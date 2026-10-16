// Compiled only by the explicitly isolated profiles; no runtime I/O.
#ifdef WORDCLOCK_EXPECT_TEST_MODE
#include <Arduino.h>
#include <NeoPixelBus.h>
#include "Config.h"
#include "WordClockState.h"
#include "ClockTestPolicy.h"
#if !defined(ESP32) || !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "Isolated build checks require ESP32-S3"
#endif
static_assert(WORDCLOCK_EXPECT_TEST_MODE == 1 || WORDCLOCK_EXPECT_TEST_MODE == 2, "Invalid expected test mode");
static_assert(clockTestPolicy::MODE == WORDCLOCK_EXPECT_TEST_MODE, "Wrong build mode");
static_assert(clockTestPolicy::IS_TEST && !clockTestPolicy::MATRIX_OUTPUT && !clockTestPolicy::PREFIX_OUTPUT, "External LED outputs must be disabled");
static_assert(!clockTestPolicy::BUTTON_INPUTS && !clockTestPolicy::BRIGHTNESS_SENSORS, "External inputs must be disabled");
static_assert(clockTestPolicy::RTC == (WORDCLOCK_EXPECT_TEST_MODE == 2), "Wrong RTC capability");
static_assert(clockTestPolicy::ONBOARD_OUTPUT && clockTestPolicy::ONBOARD_GPIO == 48, "Wrong onboard diagnostic capability");
static_assert(clockTestPolicy::RTC_SDA == 8 && clockTestPolicy::RTC_SCL == 9 && clockTestPolicy::RTC_ADDRESS == 0x68, "Wrong RTC-only bus");
#endif
