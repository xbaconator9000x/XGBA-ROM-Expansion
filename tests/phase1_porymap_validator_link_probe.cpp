#include "validator.h"

int main()
{
    PrefixValidator validator(QStringLiteral("g"));
    validator.setPrefix(QStringLiteral("e"));
    return 0;
}
