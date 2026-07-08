idf_component_register(
    SRCS "NetworkManager.cpp"
    INCLUDE_DIRS include
    REQUIRES config status esp_event esp_netif esp_wifi freertos
)
