#include "BrightnessSchedule.h"
#include <assert.h>
#include <math.h>
using namespace brightnessSchedule;
static uint32_t at(unsigned h, unsigned m, unsigned s = 0) {
    return ((h * 60UL + m) * 60UL + s) * 1000UL;
}
static void near(float actual, float expected) {
    assert(fabsf(actual - expected) < 0.001f);
}
int main() {
    Schedule s = {};
    s.defaultTenths = 400;
    assert(valid(s));
    near(percent(s, at(12, 0), true), 40.f);
    near(percent(s, 0, false), 40.f);
    s.count = 3;
    s.events[0] = {420, 400, 10};
    s.events[1] = {1185, 100, 15};
    s.events[2] = {1230, 0, 5};
    assert(valid(s));
    near(percent(s, at(19, 44), true), 40.f);
    near(percent(s, at(19, 45), true), 40.f);
    near(percent(s, at(19, 52, 30), true), 25.f);
    near(percent(s, at(20, 0), true), 10.f);
    near(percent(s, at(20, 29), true), 10.f);
    near(percent(s, at(20, 30), true), 10.f);
    near(percent(s, at(20, 32, 30), true), 5.f);
    near(percent(s, at(20, 35), true), 0.f);
    near(percent(s, at(0, 0), true), 0.f);
    near(percent(s, at(6, 59), true), 0.f);
    near(percent(s, at(7, 5), true), 20.f);
    near(percent(s, at(7, 10), true), 40.f);
    near(percent(s, at(12, 0), false), 0.f);
    near(percent(s, at(19, 52, 30), true), percent(s, at(19, 52, 30), true));
    Schedule bad = s;
    bad.count = 17; assert(!valid(bad));
    bad = s; bad.events[1].minute = 420; assert(!valid(bad));
    bad = s; bad.events[1].fadeMinutes = 46; assert(!valid(bad));
    bad = s; bad.events[0].targetTenths = 1001; assert(!valid(bad));
    near(percent(bad, at(12, 0), true), 0.f);
    Schedule wrap = {};
    wrap.defaultTenths = 400;
    wrap.count = 2;
    wrap.events[0] = {420, 400, 0};
    wrap.events[1] = {1430, 100, 20};
    assert(valid(wrap));
    near(percent(wrap, at(0, 0), true), 25.f);
    near(percent(wrap, at(0, 10), true), 10.f);
    Schedule fraction = {};
    fraction.defaultTenths = 5;
    near(percent(fraction, 0, true), 0.5f);
    const uint8_t uniform[8] = {30,30,30,30,30,30,30,30};
    Schedule migrated = {};
    assert(fromLegacy(uniform, migrated));
    assert(migrated.count == 0); near(percent(migrated, 0, true), 30.f);
    const uint8_t varied[8] = {10,20,30,40,50,60,70,80};
    assert(fromLegacy(varied, migrated)); assert(migrated.count == 8);
    near(percent(migrated, at(0, 0), true), 10.f);
    near(percent(migrated, at(7, 0), true), 20.f);
    near(percent(migrated, at(23, 0), true), 80.f);
    const uint8_t corrupt[8] = {255,20,30,40,50,60,70,80};
    assert(!fromLegacy(corrupt, migrated)); assert(migrated.count == 8);
    return 0;
}
