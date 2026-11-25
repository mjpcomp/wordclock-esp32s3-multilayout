#include "BootButtonGestureModel.h"
#include <cassert>
#include <stdint.h>
using bootButtonGesture::Action;
using bootButtonGesture::Model;

void none(Model &m, uint32_t now, bool pressed, bool enabled = false) {
    assert(m.sample(now, pressed, enabled) == Action::None);
}
Action hold(Model &m, uint32_t base, uint32_t duration, bool enabled) {
    none(m, base, false, enabled);
    none(m, base + 100, true, enabled);
    none(m, base + 140, true, enabled);
    none(m, base + 100 + duration, false, enabled);
    none(m, base + 139 + duration, false, enabled);
    const Action result = m.sample(base + 140 + duration, false, enabled);
    none(m, base + 141 + duration, false, enabled);
    none(m, base + 240 + duration, false, enabled);
    return result;
}

int main() {
    const uint32_t durations[] = {1999, 2000, 7999, 8000, 20000};
    for (unsigned option = 0; option < 2; ++option) {
        for (uint32_t duration : durations) {
            const Action expected = duration >= 8000 ? Action::WiFiSetup
                : option && duration >= 2000 ? Action::NextMode : Action::None;
            Model fresh;
            assert(hold(fresh, 0, duration, option != 0) == expected);
            Model wrap;
            assert(hold(wrap, UINT32_MAX - 1000, duration, option != 0) == expected);
        }
    }
    {
        Model m;
        none(m, 0, false);
        none(m, 100, true);
        none(m, 120, false);
        none(m, 160, false);
        none(m, 200, true, true);
        none(m, 220, false, true);
        none(m, 230, true, true);
        none(m, 269, true, true);
        none(m, 270, true, true);
        none(m, 2230, false, true);
        none(m, 2269, false, true);
        assert(m.sample(2270, false, true) == Action::NextMode);
        none(m, 2300, false, true);
    }
    {
        Model m;
        none(m, 0, false, true);
        none(m, 100, true, true);
        none(m, 140, true, true);
        none(m, 2100, false, true);
        none(m, 2120, true, true);
        none(m, 2140, false, true);
        none(m, 2179, false, true);
        assert(m.sample(2180, false, true) == Action::NextMode);
        none(m, 2220, false, true);
    }
    {
        Model m;
        none(m, 0, true, true);
        none(m, 9000, true, true);
        none(m, 9100, false, true);
        none(m, 9140, false, true);
        assert(hold(m, 10000, 2000, true) == Action::NextMode);
        assert(hold(m, 13000, 8000, false) == Action::WiFiSetup);
    }
    {
        Model m;
        none(m, 0, false, true);
        none(m, 100, true, true);
        none(m, 140, true, true);
        none(m, 2140, true, false);
        none(m, 8140, true, false);
        none(m, 9000, false, false);
        assert(m.sample(9040, false, false) == Action::WiFiSetup);
        none(m, 20000, false, true);
    }
    for (unsigned option = 0; option < 2; ++option) {
        Model m;
        const bool enabled = option != 0;
        none(m, 0, false, enabled);
        none(m, 100, true, enabled);
        none(m, 140, true, enabled);
        none(m, 1000, true, !enabled);
        none(m, 2100, false, !enabled);
        assert(m.sample(2140, false, !enabled) ==
               (enabled ? Action::NextMode : Action::None));
    }
    {
        Model m;
        none(m, 0, false, true);
        none(m, 100, true, true);
        none(m, 140, true, true);
        m.reset();
        none(m, 9000, true, true);
        none(m, 9100, false, true);
        none(m, 9140, false, true);
        assert(hold(m, 10000, 2000, true) == Action::NextMode);
    }
    {
        Model m;
        none(m, 0, false, true);
        none(m, 100, true, true);
        none(m, 140, true, true);
        none(m, 8140, true, true);
        none(m, UINT32_MAX - 100, true, true);
        none(m, 1000, true, true);
        none(m, 2100, false, true);
        assert(m.sample(2140, false, true) == Action::WiFiSetup);
    }
}
