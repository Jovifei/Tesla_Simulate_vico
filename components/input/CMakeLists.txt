idf_component_register(
    SRCS Encoder.cpp ThrottlePot.cpp
    INCLUDE_DIRS include
    REQUIRES driver esp_driver_gpio esp_adc esp_timer config
)
