idf_component_register(
    SRCS "OtaManager.cpp"
    INCLUDE_DIRS include
    REQUIRES app_update config esp_event esp_http_client esp_https_ota esp_netif esp_wifi status
)
