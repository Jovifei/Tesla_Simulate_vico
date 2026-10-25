#pragma once
class Engine;
namespace offline {
// Read-only taps. No additional random calls or changes to physical equations.
extern void (*source)(Engine *, const double *, int);
extern void (*audio)(float, float, float, float, float, float);
}
