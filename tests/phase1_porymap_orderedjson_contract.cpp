#include "orderedjson.h"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

static void check(bool ok, const char *message) {
    if (!ok) {
        std::fprintf(stderr, "PHASE1_ORDEREDJSON_FATAL %s\n", message);
        std::exit(2);
    }
}

int main() {
    QString error;
    OrderedJson malformed = OrderedJson::parse(QString("{\"key\":"), &error);
    check(malformed.is_null() && !error.isEmpty(), "truncated_input_error");

    error.clear();
    OrderedJson trailing = OrderedJson::parse(QString("{\"key\":1} trailing"), &error);
    check(trailing.is_null() && !error.isEmpty(), "trailing_input_error");

    error.clear();
    OrderedJson standardComment = OrderedJson::parse(QString("{/* comment */\"key\":1}"), &error);
    check(standardComment.is_null() && !error.isEmpty(), "standard_comment_rejected");

    error.clear();
    OrderedJson comment = OrderedJson::parse(
        QString("{/* comment */\"key\":1}"), &error, poryjson::JsonParse::COMMENTS);
    check(comment.is_object() && error.isEmpty(), "comments_mode_accepts_comment");

    error.clear();
    OrderedJson duplicate = OrderedJson::parse(
        QString("{\"first\":1,\"second\":2,\"first\":3}"), &error);
    check(duplicate.is_object() && error.isEmpty(), "duplicate_key_parse");
    const auto &members = duplicate.object_items();
    check(members.size() == 2, "duplicate_key_count");
    auto member = members.cbegin();
    check(member->first == QString("first") && member->second.int_value() == 3,
          "duplicate_key_last_value_keeps_first_position");
    ++member;
    check(member->first == QString("second") && member->second.int_value() == 2,
          "insertion_order_preserved");
    const QString serialized = duplicate.dump();
    check(serialized.indexOf("\"first\"") < serialized.indexOf("\"second\""),
          "dump_insertion_order");

    error.clear();
    OrderedJson arrayRoot = OrderedJson::parse(QString("[]"), &error);
    check(arrayRoot.is_array() && error.isEmpty() && arrayRoot.object_items().empty(),
          "valid_non_object_root_is_not_a_parse_error");

    OrderedJson fractional = OrderedJson::fromQJsonValue(QJsonValue(1.75));
    check(fractional.is_number() && fractional.int_value() == 1,
          "qjson_double_conversion_truncates_to_integer");

    OrderedJson::object firstObject;
    firstObject["same"] = "first";
    OrderedJson first(firstObject);
    OrderedJson::object secondObject;
    secondObject["same"] = "second";
    OrderedJson second(secondObject);
    const QString firstValue = first[QString("same")].string_value();
    const QString secondValue = second[QString("same")].string_value();
    check(firstValue == QString("first"), "first_object_lookup");
    check(secondValue == QString("first"), "pinned_static_iterator_cross_object_behavior");

    std::puts("PHASE1_ORDEREDJSON_RESULT malformed=reject trailing=reject comments=explicit duplicate=last-value-first-position root-array=valid-empty-object-view qjson-double=truncated static-lookup=first-object");
    return 0;
}
