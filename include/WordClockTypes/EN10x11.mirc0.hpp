#pragma once

#include "ClockType.hpp"

// Creator: Mirc0.
// https://makerworld.com/en/@Mirc0. (the creator name includes the final period)
// https://makerworld.com/en/models/2461080-word-clock-with-esp32-rtc-web-interface
// Physical front and supplied pixel assignments credited to Mirc0.
// This class must be registered separately before it is selectable.

/*
 *           Layout Front
 *                COL
 *       X 9 8 7 6 5 4 3 2 1 0
 * ROW + - - - - - - - - - - -
 *  0  | I T K I S M O W I F I
 *  1  | A C Q U A R T E R D G
 *  2  | T W E N T Y F I V E L
 *  3  | H A L F B T E N F T O
 *  4  | P A S T A E L N I N E
 *  5  | O N E S I X T H R E E
 *  6  | F O U R F I V E T W O
 *  7  | E I G H T E L E V E N
 *  8  | S E V E N T W E L V E
 *  9  | T E N S E O C L O C K
 */

// Supplied LED indices imply serpentine rows: even L->R, odd R->L.
// The COL labels above are right-origin bit positions, not strip indices.
class Mirc0En10x11_t : public ClockType {
public:
    LanguageAbbreviation usedLang() override { return LanguageAbbreviation::EN; }
    bool hasTwenty() override { return true; }
    bool hasTwentyfive() override { return true; }
    bool hasAQuarter() override { return false; }
    bool hasLed7x() override { return false; }
    bool hasMinuteCorners() override { return false; }
    bool hasSecondsFrame() override { return false; }
    uint8_t numPixelsFrameMatrix() override { return 0; }

    void getMinuteArray(uint16_t *out, uint8_t variant) override {
        (void)variant;
        for (uint8_t i = 0; i < 4; ++i) out[i] = 110 + i;
    }

    void show(FrontWord word) override {
        switch (word) {
        case FrontWord::es_ist: range(0, 2); range(3, 2); break;
        case FrontWord::uhr: range(99, 6); break;
        case FrontWord::min_5: range(28, 4); break;
        case FrontWord::min_10: range(36, 3); break;
        case FrontWord::min_20: range(22, 6); break;
        case FrontWord::min_25: range(22, 10); break;
        case FrontWord::viertel: range(13, 7); break;
        case FrontWord::halb: range(40, 4); break;
        case FrontWord::nach:
        case FrontWord::v_nach: range(44, 4); break;
        case FrontWord::vor:
        case FrontWord::v_vor: range(33, 2); break;
        case FrontWord::hour_1: range(63, 3); break;
        case FrontWord::hour_2: range(74, 3); break;
        case FrontWord::hour_3: range(55, 5); break;
        case FrontWord::hour_4: range(66, 4); break;
        case FrontWord::hour_5: range(70, 4); break;
        case FrontWord::hour_6: range(60, 3); break;
        case FrontWord::hour_7: range(88, 5); break;
        case FrontWord::hour_8: range(83, 5); break;
        case FrontWord::hour_9: range(51, 4); break;
        case FrontWord::hour_10: range(107, 3); break;
        case FrontWord::hour_11: range(77, 6); break;
        case FrontWord::hour_12: range(93, 6); break;
        default: break;
        }
    }

private:
    void range(uint8_t first, uint8_t count) {
        for (uint16_t i = first; i < uint16_t(first) + count && i < 110; ++i) {
            if (i >= 7 && i <= 10) continue;
            uint8_t row = i / 11;
            uint8_t physicalCol = i % 11;
            uint8_t visualCol = (row % 2) ? 10 - physicalCol : physicalCol;
            setFrontMatrixPixel(row, 10 - visualCol);
        }
    }
};

Mirc0En10x11_t _mirc0_en10x11;
