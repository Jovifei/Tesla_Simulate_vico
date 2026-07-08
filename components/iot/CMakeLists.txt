idf_component_register(
    SRCS "IotManager.cpp"
    INCLUDE_DIRS include
    REQUIRES mqtt config status ota domain json freertos
)
