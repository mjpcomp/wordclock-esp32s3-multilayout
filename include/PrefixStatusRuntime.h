#pragma once
#include "LedStatusPrefix.h"

namespace prefixStatusRuntime {
#if WORDCLOCK_ENABLE_PREFIX_STATUS_PIXEL
void noteTimeSet();
void resetDisplay();
void service();
#else
inline void noteTimeSet() {}
inline void resetDisplay() {}
inline void service() {}
#endif
} // namespace prefixStatusRuntime
