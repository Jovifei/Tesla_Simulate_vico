idf_component_register(
    SRCS Ws2812Led.cpp
    INCLUDE_DIRS include
    REQUIRES driver esp_driver_rmt config
)
