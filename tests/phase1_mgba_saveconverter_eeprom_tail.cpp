#include <QByteArray>
#include <QList>

#include <mgba-util/common.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>

namespace QGBA {

enum mPlatform {
	mPLATFORM_NONE,
	mPLATFORM_GBA,
	mPLATFORM_GB
};

enum class Endian {
	NONE,
	LITTLE,
	BIG
};

enum GBASavedataType {
	GBA_SAVEDATA_EEPROM,
	GBA_SAVEDATA_EEPROM512,
	GBA_SAVEDATA_SRAM,
	GBA_SAVEDATA_FLASH512,
	GBA_SAVEDATA_FLASH1M
};

enum class Container {
	NONE,
	SAVESTATE,
	SHARKPORT,
	GSV
};

static constexpr ssize_t GBA_SIZE_EEPROM = 0x2000;
static constexpr ssize_t GBA_SIZE_EEPROM512 = 0x200;
static constexpr ssize_t GBA_SIZE_SRAM = 0x8000;
static constexpr ssize_t GBA_SIZE_FLASH512 = 0x10000;
static constexpr ssize_t GBA_SIZE_FLASH1M = 0x20000;

struct VFileDevice {
	explicit VFileDevice(QByteArray bytes)
		: bytes(std::move(bytes)) {}

	qint64 size() const { return bytes.size(); }
	bool seek(qint64 position) {
		if (position < 0 || position > bytes.size()) {
			return false;
		}
		cursor = position;
		return true;
	}
	QByteArray readAll() {
		QByteArray result = bytes.mid(cursor);
		cursor = bytes.size();
		return result;
	}
	QByteArray read(qint64 count) {
		QByteArray result = bytes.mid(cursor, count);
		cursor += result.size();
		return result;
	}

	QByteArray bytes;
	qint64 cursor = 0;
};

struct SaveConverter {
	struct AnnotatedSave {
		AnnotatedSave()
			: container(Container::NONE), platform(mPLATFORM_NONE), size(0),
			  endianness(Endian::NONE), gba{GBA_SAVEDATA_EEPROM} {}
		AnnotatedSave(GBASavedataType type,
		              std::shared_ptr<VFileDevice> file,
		              Endian endian = Endian::NONE,
		              Container container = Container::NONE)
			: container(container), platform(mPLATFORM_GBA), size(file->size()),
			  backing(std::move(file)), endianness(endian), gba{type} {}

		AnnotatedSave asRaw() const;
		bool operator==(const AnnotatedSave& other) const;
		QList<AnnotatedSave> possibleConversions() const;
		QByteArray convertTo(const AnnotatedSave& target) const;

		Container container;
		mPlatform platform;
		ssize_t size;
		std::shared_ptr<VFileDevice> backing;
		Endian endianness;
		struct {
			GBASavedataType type;
		} gba;
	};

	void detectFromSize(std::shared_ptr<VFileDevice> vf);
	QList<AnnotatedSave> m_validSaves;
};

}

#define M_CORE_GBA
struct TestLogger {
	template<typename T>
	TestLogger& operator<<(const T&) { return *this; }
};
#define LOG(...) TestLogger()
#define tr(text) text

namespace QGBA {
PHASE1_INSERT_PINNED_DETECT_FROM_SIZE
PHASE1_INSERT_PINNED_AS_RAW
PHASE1_INSERT_PINNED_ANNOTATED_EQUALITY
PHASE1_INSERT_PINNED_POSSIBLE_CONVERSIONS
PHASE1_INSERT_PINNED_CONVERT_TO
}

static QByteArray makeInput(int payloadSize, uint8_t sentinel) {
	QByteArray bytes(payloadSize + 16, Qt::Uninitialized);
	for (int offset = 0; offset < payloadSize; ++offset) {
		bytes[offset] = static_cast<char>((offset * 37 + offset / 8 + 11) & 0xFF);
	}
	for (int offset = payloadSize; offset < bytes.size(); ++offset) {
		bytes[offset] = static_cast<char>(sentinel + offset - payloadSize);
	}
	return bytes;
}

static bool expectDetection(ssize_t size, int expectedCount) {
	auto bytes = QByteArray(static_cast<int>(size), '\x5A');
	QGBA::SaveConverter converter;
	converter.detectFromSize(std::make_shared<QGBA::VFileDevice>(bytes));
	return converter.m_validSaves.size() == expectedCount;
}

static QGBA::SaveConverter::AnnotatedSave detectInput(QByteArray bytes,
                                                       QGBA::GBASavedataType type) {
	QGBA::SaveConverter converter;
	converter.detectFromSize(std::make_shared<QGBA::VFileDevice>(bytes));
	for (const auto& candidate : converter.m_validSaves) {
		if (candidate.gba.type == type && candidate.endianness == QGBA::Endian::LITTLE) {
			return candidate;
		}
	}
	std::abort();
}

static bool checkPayload(const QByteArray& original, const QByteArray& converted,
                         int payloadSize, bool swapped) {
	if (converted.size() != original.size()) {
		return false;
	}
	for (int offset = 0; offset < payloadSize; ++offset) {
		const int inOffset = swapped ? (offset & ~7) + (7 - (offset & 7)) : offset;
		if (converted[offset] != original[inOffset]) {
			return false;
		}
	}
	return true;
}

static int runCase(const char* label, int payloadSize,
                   QGBA::GBASavedataType type, uint8_t sentinel) {
	const QByteArray original = makeInput(payloadSize, sentinel);
	const auto input = detectInput(original, type);
	const auto conversions = input.possibleConversions();
	const QGBA::SaveConverter::AnnotatedSave* swapped = nullptr;
	for (const auto& candidate : conversions) {
		if (candidate.platform == QGBA::mPLATFORM_GBA &&
		    candidate.gba.type == type &&
		    candidate.size == original.size() &&
		    candidate.endianness == QGBA::Endian::BIG) {
			swapped = &candidate;
			break;
		}
	}
	if (!swapped) {
		return 1;
	}
	const QByteArray converted = input.convertTo(*swapped);
	if (!checkPayload(original, converted, payloadSize, true)) {
		return 2;
	}
	bool tailWasPreserved = true;
	for (int offset = payloadSize; offset < original.size(); ++offset) {
		tailWasPreserved &= converted[offset] == original[offset];
	}

	auto reverseBacking = std::make_shared<QGBA::VFileDevice>(converted);
	QGBA::SaveConverter::AnnotatedSave reverseInput(
		type, reverseBacking, QGBA::Endian::BIG);
	auto reverseTarget = reverseInput;
	reverseTarget.backing.reset();
	reverseTarget.endianness = QGBA::Endian::LITTLE;
	const QByteArray roundTrip = reverseInput.convertTo(reverseTarget);
	if (!checkPayload(original, roundTrip, payloadSize, false)) {
		return 3;
	}
	bool roundTripTailWasPreserved = true;
	for (int offset = payloadSize; offset < original.size(); ++offset) {
		roundTripTailWasPreserved &= roundTrip[offset] == original[offset];
	}

	std::printf(
		"PHASE1_EEPROM_CASE %s size=%d payload=%d source_tail=%s "
		"converted_tail_hex=%s converted_tail_preserved=%d "
		"roundtrip_tail_preserved=%d payload_roundtrip=PASS\n",
		label, static_cast<int>(original.size()), payloadSize,
		QByteArray(original.constData() + payloadSize, 16).toHex().constData(),
		QByteArray(converted.constData() + payloadSize, 16).toHex().constData(),
		tailWasPreserved ? 1 : 0,
		roundTripTailWasPreserved ? 1 : 0);
	return 0;
}

int main() {
	if (!expectDetection(QGBA::GBA_SIZE_EEPROM, 2) ||
	    !expectDetection(QGBA::GBA_SIZE_EEPROM + 16, 2) ||
	    !expectDetection(QGBA::GBA_SIZE_EEPROM - 1, 0) ||
	    !expectDetection(QGBA::GBA_SIZE_EEPROM + 17, 0) ||
	    !expectDetection(QGBA::GBA_SIZE_EEPROM512, 2) ||
	    !expectDetection(QGBA::GBA_SIZE_EEPROM512 + 16, 2) ||
	    !expectDetection(QGBA::GBA_SIZE_EEPROM512 - 1, 0) ||
	    !expectDetection(QGBA::GBA_SIZE_EEPROM512 + 17, 0)) {
		std::fprintf(stderr, "EEPROM size detector boundary control failed\n");
		return 4;
	}
	const int small = runCase("eeprom512_plus16", QGBA::GBA_SIZE_EEPROM512,
	                          QGBA::GBA_SAVEDATA_EEPROM512, 0xA0);
	const int large = runCase("eeprom8k_plus16", QGBA::GBA_SIZE_EEPROM,
	                          QGBA::GBA_SAVEDATA_EEPROM, 0xC0);
	if (small || large) {
		std::fprintf(stderr, "EEPROM conversion case failed: %d %d\n", small, large);
		return 5;
	}
	std::puts("PHASE1_EEPROM_DONE");
	return 0;
}
