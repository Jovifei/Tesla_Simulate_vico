idf_component_register(
    SRCS "BleService.cpp"
    INCLUDE_DIRS include
    REQUIRES bt config domain json ota
    PRIV_REQUIRES nvs_flash
)
