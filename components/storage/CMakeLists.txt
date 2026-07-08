idf_component_register(
    SRCS SdConfigStore.cpp
    INCLUDE_DIRS include
    REQUIRES fatfs sdmmc driver json config
)
