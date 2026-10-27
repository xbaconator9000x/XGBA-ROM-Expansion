// Source-grounded minimal C++ reproducer for pinned pret/pokefirered
// tools/mapjson/mapjson.cpp (blob 8d8ec4e4e6e1c011b06f00819abe40bad10d19d5)
// generate_connections_text, lines 470-479.
//
// This reproduces only the invalid iterator-advance expression, NOT the full
// mapjson binary, its actual input reachability, or editor/runtime effects.
//
// Compile: g++ -std=c++17 -D_GLIBCXX_DEBUG -O0 -g tools/fixtures/mapjson_partial_connection_order_debug.cpp -o /tmp/xgba-mapjson-order
// Positive control: /tmp/xgba-mapjson-order present     # exit 0
// Negative control: /tmp/xgba-mapjson-order missing     # libstdc++ debug iterator assertion; nonzero exit
#include <algorithm>
#include <limits>
#include <string>
#include <vector>

int main(int argc, char **argv) {
    if (argc != 2)
        return 2;

    std::vector<std::string> connections_include_order{"A", "B"};
    std::string a = "A";
    std::string b = std::string(argv[1]) == "present" ? "B" : "MISSING";

    // The expression and absent-element handling are copied from the pinned
    // generator's comparator; std::string stands in for its JSON string value.
    auto iter_a = std::find(connections_include_order.begin(), connections_include_order.end(), a);
    if (iter_a == connections_include_order.end())
        iter_a = connections_include_order.begin() + std::numeric_limits<int>::max();
    auto iter_b = std::find(connections_include_order.begin(), connections_include_order.end(), b);
    if (iter_b == connections_include_order.end())
        iter_b = connections_include_order.begin() + std::numeric_limits<int>::max();
    return iter_a < iter_b ? 0 : 1;
}
