# Engine-Sim Research

URL: https://github.com/ange-yaghi/engine-sim
Pinned commit: `85f7c3b959a908ed5232ede4f1a4ac7eafe6b630`
License: MIT.

Clean-room conclusion: use event → chamber → path → collector topology as
research context; do not copy C++, `.mr`, IR, audio, or OEM claims.
All five fixed submodules were checked out. Docker CMake configured with its
policy override, but the actual build fails in delta-studio's Windows/MSVC-only
interfaces (`Windows.h`, `_aligned_malloc`, `__declspec`, `__forceinline`);
CTest therefore has no test binary. No upstream patch or binary is claimed.
