#include "validator.h"

#include <QCoreApplication>

#include <iostream>

namespace {

bool expect(bool condition, const char *label)
{
    if (!condition)
        std::cerr << "VALIDATOR_ASSERTION_FAILED=" << label << '\n';
    return condition;
}

QValidator::State stateOf(const QValidator &validator, const QString &text)
{
    QString input = text;
    int position = input.size();
    return validator.validate(input, position);
}

}

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    IdentifierValidator identifier;
    bool ok = true;

    ok &= expect(stateOf(identifier, QStringLiteral("Map_1")) == QValidator::Acceptable,
                 "plain_identifier_accepted");
    ok &= expect(stateOf(identifier, QStringLiteral("_Map9")) == QValidator::Acceptable,
                 "underscore_identifier_accepted");
    ok &= expect(stateOf(identifier, QStringLiteral("9Map")) == QValidator::Invalid,
                 "leading_digit_rejected");
    ok &= expect(stateOf(identifier, QStringLiteral("Map-1")) == QValidator::Invalid,
                 "punctuation_rejected");
    ok &= expect(stateOf(identifier, QString()) == QValidator::Intermediate,
                 "empty_identifier_is_intermediate_by_default");
    identifier.setAllowEmpty(true);
    ok &= expect(stateOf(identifier, QString()) == QValidator::Acceptable,
                 "empty_identifier_allowed_when_configured");
    ok &= expect(stateOf(identifier, QStringLiteral("Map")) == QValidator::Acceptable,
                 "identifier_remains_valid_after_allow_empty");

    IdentifierValidator prefixed(QStringLiteral("g"));
    ok &= expect(stateOf(prefixed, QStringLiteral("gMap_1")) == QValidator::Acceptable,
                 "prefixed_identifier_accepted");
    ok &= expect(stateOf(prefixed, QStringLiteral("Map_1")) == QValidator::Intermediate,
                 "valid_identifier_without_prefix_is_intermediate");
    ok &= expect(stateOf(prefixed, QStringLiteral("9Map")) == QValidator::Intermediate,
                 "invalid_identifier_recoverable_by_prefix_is_intermediate");
    ok &= expect(stateOf(prefixed, QStringLiteral("g")) == QValidator::Acceptable,
                 "prefix_only_is_valid_identifier");
    ok &= expect(!prefixed.isValid(QStringLiteral("Map_1")),
                 "is_valid_requires_prefix");
    ok &= expect(prefixed.isValid(QStringLiteral("gMap_1")),
                 "is_valid_accepts_prefixed_identifier");

    QString missingPrefix = QStringLiteral("Map_1");
    prefixed.fixup(missingPrefix);
    ok &= expect(missingPrefix == QStringLiteral("gMap_1"),
                 "fixup_prepends_missing_prefix");
    QString invalidBody = QStringLiteral("9Map");
    prefixed.fixup(invalidBody);
    ok &= expect(invalidBody == QStringLiteral("g9Map"),
                 "fixup_can_make_leading_digit_valid_after_prefix");

    UppercaseValidator uppercase;
    const QValidator &uppercaseInterface = uppercase;
    QString lowercase = QStringLiteral("ab_9z");
    int position = lowercase.size();
    ok &= expect(uppercaseInterface.validate(lowercase, position) == QValidator::Acceptable &&
                     lowercase == QStringLiteral("AB_9Z"),
                 "uppercase_validator_mutates_and_accepts");

    if (ok)
        std::cout << "VALIDATOR_NATIVE plain_ids=1 prefix_states=1 fixup=1 "
                     "uppercase=1 invalid_cases=2\n";
    return ok ? 0 : 1;
}
