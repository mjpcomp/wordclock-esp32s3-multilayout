#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>

uint32_t frontMatrix[22] = {};
enum class BuildTypeDef : uint8_t { Normal, DoubleResM1 };
enum class MinuteVariant : uint8_t { Off, LED4x, LED7x, Corners, InWords };
enum { FlipHorzVert, MeanderRows, ExtraLedPerRow };
struct { BuildTypeDef buildTypeDef = BuildTypeDef::Normal; bool layoutVariant[6] = {}; } G;
struct { void printf(const char *, ...) {} } Serial;
#include "EN10x11.mirc0.hpp"

const char *FRONT[] = {
    "ITKISMOWIFI", "ACQUARTERDG", "TWENTYFIVEL", "HALFBTENFTO", "PASTAELNINE",
    "ONESIXTHREE", "FOURFIVETWO", "EIGHTELEVEN", "SEVENTWELVE", "TENSEOCLOCK"
};

static void checkLetters(FrontWord word, const char *expected) {
    std::memset(frontMatrix, 0, sizeof(frontMatrix));
    _mirc0_en10x11.show(word);
    std::string actual;
    for (unsigned r = 0; r < 10; ++r)
        for (unsigned c = 0; c < 11; ++c)
            if (_mirc0_en10x11.getFrontMatrixPixel(r, c)) actual += FRONT[r][c];
    assert(actual == expected);
}

static void drawTime(unsigned h, unsigned m) {
    std::memset(frontMatrix, 0, sizeof(frontMatrix));
    auto &clock = _mirc0_en10x11;
    clock.show(FrontWord::es_ist);
    unsigned rounded = (m / 5) * 5;
    unsigned spoken = (h + (rounded >= 35)) % 12;
    static const FrontWord hours[] = {
        FrontWord::hour_12, FrontWord::hour_1, FrontWord::hour_2,
        FrontWord::hour_3, FrontWord::hour_4, FrontWord::hour_5,
        FrontWord::hour_6, FrontWord::hour_7, FrontWord::hour_8,
        FrontWord::hour_9, FrontWord::hour_10, FrontWord::hour_11
    };
    clock.show(hours[spoken]);
    switch (rounded) {
    case 0: clock.show(FrontWord::uhr); break;
    case 5: case 55: clock.show(FrontWord::min_5); break;
    case 10: case 50: clock.show(FrontWord::min_10); break;
    case 15: case 45: clock.show(FrontWord::viertel); break;
    case 20: case 40: clock.show(FrontWord::min_20); break;
    case 25: case 35: clock.show(FrontWord::min_25); break;
    case 30: clock.show(FrontWord::halb); break;
    }
    if (rounded) clock.show(rounded >= 35 ? FrontWord::vor : FrontWord::nach);
}

int main() {
    auto &clock = _mirc0_en10x11;
    G.layoutVariant[MeanderRows] = true;
    assert(clock.usedLang() == LanguageAbbreviation::EN);
    assert(clock.rowsWordMatrix() == 10 && clock.colsWordMatrix() == 11);
    assert(clock.supportedMinuteVariantMask() == 3);
    assert(!clock.hasSecondsFrame() && clock.numPixelsFrameMatrix() == 0);
    struct WordCase { FrontWord word; const char *letters; };
    const WordCase cases[] = {
        {FrontWord::es_ist,"ITIS"}, {FrontWord::uhr,"OCLOCK"},
        {FrontWord::min_5,"FIVE"}, {FrontWord::min_10,"TEN"},
        {FrontWord::min_20,"TWENTY"}, {FrontWord::min_25,"TWENTYFIVE"},
        {FrontWord::viertel,"QUARTER"}, {FrontWord::halb,"HALF"},
        {FrontWord::nach,"PAST"}, {FrontWord::vor,"TO"},
        {FrontWord::hour_1,"ONE"}, {FrontWord::hour_2,"TWO"},
        {FrontWord::hour_3,"THREE"}, {FrontWord::hour_4,"FOUR"},
        {FrontWord::hour_5,"FIVE"}, {FrontWord::hour_6,"SIX"},
        {FrontWord::hour_7,"SEVEN"}, {FrontWord::hour_8,"EIGHT"},
        {FrontWord::hour_9,"NINE"}, {FrontWord::hour_10,"TEN"},
        {FrontWord::hour_11,"ELEVEN"}, {FrontWord::hour_12,"TWELVE"}
    };
    for (const auto &test : cases) checkLetters(test.word, test.letters);
    uint16_t dots[4]; clock.getMinuteArray(dots, 0);
    for (unsigned i = 0; i < 4; ++i) assert(dots[i] == 110 + i);
    for (unsigned h = 0; h < 24; ++h) {
        for (unsigned m = 0; m < 60; ++m) {
            drawTime(h, m);
            std::cout << h << ':' << m << ':';
            for (unsigned r = 0; r < 10; ++r) {
                for (unsigned c = 0; c < 11; ++c) {
                    if (!clock.getFrontMatrixPixel(r, c)) continue;
                    unsigned i = clock.getFrontMatrixIndex(r, c);
                    assert(i < 110 && !(i >= 7 && i <= 10));
                    std::cout << i << ',';
                }
            }
            for (unsigned i = 0; i < m % 5; ++i) std::cout << dots[i] << ',';
            std::cout << '\n';
        }
    }
    std::memset(frontMatrix, 0, sizeof(frontMatrix));
    clock.show(FrontWord::error);
    clock.show(FrontWord::a_quarter);
    clock.show(FrontWord::happy_birthday);
    for (uint32_t row : frontMatrix) assert(row == 0);
}
