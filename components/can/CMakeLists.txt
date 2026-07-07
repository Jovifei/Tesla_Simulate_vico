idf_component_register(
    SRCS TwaiCanSource.cpp CanFrames.cpp
    INCLUDE_DIRS include
    REQUIRES driver config domain
)
