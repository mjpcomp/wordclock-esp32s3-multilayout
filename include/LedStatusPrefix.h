#pragma once
#include <stdint.h>

// Hardware option: default OFF. Enable globally with a compiler build flag,
// or change this default to 1 before compiling. Never renumber layout tables.
#ifndef WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL
#define WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL 0
#endif
#if WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL != 0 && WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL != 1
#error "WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL must be 0 or 1"
#endif
namespace ledPrefix {
constexpr uint16_t COUNT = WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL;
constexpr uint16_t physicalIndex(uint16_t logicalIndex) {
    return logicalIndex + COUNT;
}
} // namespace ledPrefix
