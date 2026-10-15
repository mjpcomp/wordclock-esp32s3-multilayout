#pragma once
#include <stdint.h>
#include "LedStatusPrefix.h"

// Compile-time capabilities, never taken from EEPROM or web pin settings.
// Declarations alone do not enforce isolation: drivers/callers must use them.
// 0: normal hardware; 1: virtual clock + onboard diagnostics; 2: same + RTC.
#ifndef WORDCLOCK_TEST_MODE
#define WORDCLOCK_TEST_MODE 0
#endif
#if WORDCLOCK_TEST_MODE != 0 && WORDCLOCK_TEST_MODE != 1 && WORDCLOCK_TEST_MODE != 2
#error "WORDCLOCK_TEST_MODE must be 0, 1 or 2"
#endif
#ifndef WORDCLOCK_ENABLE_ONBOARD_STATUS_LED
#define WORDCLOCK_ENABLE_ONBOARD_STATUS_LED 0
#endif
#if WORDCLOCK_ENABLE_ONBOARD_STATUS_LED != 0 && WORDCLOCK_ENABLE_ONBOARD_STATUS_LED != 1
#error "WORDCLOCK_ENABLE_ONBOARD_STATUS_LED must be 0 or 1"
#endif

namespace clockTestPolicy {
constexpr uint8_t MODE = WORDCLOCK_TEST_MODE;
constexpr bool IS_TEST = MODE != 0;
constexpr bool MATRIX_OUTPUT = MODE == 0;
constexpr bool PREFIX_OUTPUT = MATRIX_OUTPUT && WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL;
constexpr bool ONBOARD_OUTPUT = IS_TEST || WORDCLOCK_ENABLE_ONBOARD_STATUS_LED;
constexpr bool BUTTON_INPUTS = MODE == 0;
constexpr bool BRIGHTNESS_SENSORS = MODE == 0;
constexpr bool RTC = MODE != 1;
constexpr uint8_t ONBOARD_GPIO = 48;
constexpr uint8_t RTC_SDA = 8, RTC_SCL = 9, RTC_ADDRESS = 0x68;

// These are capability gates, not normal-mode GPIO validity checks.
constexpr bool permitsOnboardPin(uint8_t pin) {
    return ONBOARD_OUTPUT && pin == ONBOARD_GPIO;
}
constexpr bool permitsI2cPins(uint8_t sda, uint8_t scl) {
    return MODE == 0 || (MODE == 2 && sda == RTC_SDA && scl == RTC_SCL);
}
constexpr bool permitsI2cAddress(uint8_t address) {
    return MODE == 0 || (MODE == 2 && address == RTC_ADDRESS);
}
} // namespace clockTestPolicy
