/* Phase 1: test-only Qt6 scaffolding for five unchanged pinned Project writers.
 * All Project::save... function bodies are injected verbatim by the verifier.
 * Empty collections are deliberate: exercises each original QFile/serializer path,
 * not full project object graph or GUI state.
 */
#include "orderedjson.h"
#include <QFile>
#include <QTemporaryDir>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QHash>
#include <QList>
#include <QStringList>
#include <QVector>
#include <QByteArray>
#include <cstdio>
#include <cstdlib>
#include <algorithm>
#include <map>
struct Layout {
    QString id, name, tileset_primary_label, tileset_secondary_label;
    QString border_path, blockdata_path;
    int width = 0, height = 0, border_width = 0, border_height = 0;
    QJsonObject customData;
};
struct Map { bool isPersistedToFile() const { return true; } };
struct LocationData {
    QString displayName;
    struct { bool valid = false; int x = 0, y = 0, width = 0, height = 0; } map;
    QJsonObject custom;
};
struct WildPokemon { int minLevel = 0, maxLevel = 0; QString species; QJsonObject customData; };
struct WildMonInfo { int encounterRate = 0; QVector<WildPokemon> wildPokemon; QJsonObject customData; };
struct WildPokemonHeader { std::map<QString, WildMonInfo> wildMons; QJsonObject customData; };
struct EncounterField {
    QString name;
    QVector<int> encounterRates;
    std::map<QString, QVector<int>> groups;
    QJsonObject customData;
};
struct HealEvent {
    QString getIdName() const { return "unused"; }
    OrderedJson::object buildEventJson(void *) const { return {}; }
};
enum class ProjectFilePath { json_layouts, json_map_groups, json_region_map_entries,
                             json_wild_encounters, json_heal_locations };
struct ProjectConfig {
    bool fail = false, useCustomBorderSize = false;
    QString getFilePath(ProjectFilePath kind) const {
        if (fail) return "dev/full";
        switch (kind) {
            case ProjectFilePath::json_layouts: return "layouts.json";
            case ProjectFilePath::json_map_groups: return "groups.json";
            case ProjectFilePath::json_region_map_entries: return "sections.json";
            case ProjectFilePath::json_wild_encounters: return "wild.json";
            case ProjectFilePath::json_heal_locations: return "heal.json";
        }
        return {};
    }
};
static void logError(const QString &) {}
struct Project {
    QString root, layoutsLabel = "gMapLayouts", wildMonTableName = "gWildMonHeaders";
    ProjectConfig projectConfig;
    QStringList orderedLayoutIdsMaster, groupNames, mapSectionIdNamesSaveOrder, healLocationSaveOrder;
    QMap<QString, Layout*> mapLayoutsMaster;
    QList<QJsonObject> failedLayoutsData;
    QJsonObject customLayoutsData, customMapGroupsData, customMapSectionsData;
    QMap<QString, QStringList> groupNameToMapNames;
    QMap<QString, Map*> maps;
    QMap<QString, LocationData> locationData;
    bool wildEncountersLoaded = true;
    QVector<EncounterField> wildMonFields;
    std::map<QString, std::map<QString, WildPokemonHeader>> wildMonData;
    QJsonObject customWildMonGroupData, customWildMonData, customHealLocationsData;
    QJsonArray extraEncounterGroups;
    QVector<QVector<HealEvent*>> healLocations;
    void ignoreWatchedFileTemporarily(const QString &) {}
    bool saveMapLayouts();
    bool saveMapGroups();
    bool saveRegionMapSections();
    bool saveWildMonData();
    bool saveHealLocations();
};
PHASE1_INSERT_PINNED_FUNCTIONS
static void require(bool condition, const char *reason) {
    if (!condition) { std::fprintf(stderr, "PHASE1_FIVE_FATAL %s\n", reason); std::exit(4); }
}
int main() {
    QTemporaryDir temp;
    require(temp.isValid(), "temporary_directory");
    Project project;
    project.root = temp.path();
    struct Test { const char *name; const char *file; const char *key; bool (Project::*writer)(); };
    const Test tests[] = {
        {"saveMapLayouts", "layouts.json", "layouts", &Project::saveMapLayouts},
        {"saveMapGroups", "groups.json", "group_order", &Project::saveMapGroups},
        {"saveRegionMapSections", "sections.json", "map_sections", &Project::saveRegionMapSections},
        {"saveWildMonData", "wild.json", "wild_encounter_groups", &Project::saveWildMonData},
        {"saveHealLocations", "heal.json", "heal_locations", &Project::saveHealLocations},
    };
    for (const Test &test : tests) {
        std::printf("PHASE1_FIVE_STAGE positive_%s\n", test.name); std::fflush(stdout);
        require((project.*test.writer)(), "positive_writer_return");
        QFile file(temp.filePath(test.file));
        require(file.open(QIODevice::ReadOnly), "positive_readback_open");
        const QByteArray bytes = file.readAll();
        QJsonParseError error;
        const QJsonDocument document = QJsonDocument::fromJson(bytes, &error);
        require(error.error == QJsonParseError::NoError && document.isObject(),
                "positive_json_parse");
        require(document.object().contains(test.key) && bytes.endsWith('\n'),
                "positive_json_key_or_newline");
        std::printf("PHASE1_FIVE_RESULT positive_%s_bytes=%lld\n",
                    test.name, (long long)bytes.size()); std::fflush(stdout);
    }
    project.root = "";
    project.projectConfig.fail = true;
    for (const Test &test : tests) {
        std::printf("PHASE1_FIVE_STAGE failed_%s\n", test.name); std::fflush(stdout);
        const bool reported = (project.*test.writer)();
        std::printf("PHASE1_FIVE_RESULT failed_%s_return=%d\n",
                    test.name, (int)reported); std::fflush(stdout);
        require(reported, "original_writer_did_not_return_success");
    }
    std::puts("PHASE1_FIVE_DONE"); std::fflush(stdout);
    return 0;
}
