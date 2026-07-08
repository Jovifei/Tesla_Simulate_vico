idf_component_register(
    SRCS "BleService.cpp"
    INCLUDE_DIRS include
    REQUIRES bt domain
    PRIV_REQUIRES nvs_flash
)
