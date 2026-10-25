/* Local AP-only configuration: no router credentials, captive portal, or uplink. */
#include "wifi_manager.h"
#include <stdio.h>
#include <string.h>
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "sdkconfig.h"
/* Refuse to compile an AP without deliberately supplied private credentials. */
_Static_assert(sizeof(CONFIG_BRIDGE_AP_PASSWORD) >= 9 && sizeof(CONFIG_BRIDGE_AP_PASSWORD) <= 64,
               "Run tools/configure_bridge.py and include sdkconfig.defaults.local");
_Static_assert(sizeof(CONFIG_BRIDGE_AP_SSID) >= 2 && sizeof(CONFIG_BRIDGE_AP_SSID) <= 33,
               "AP SSID must be 1..32 bytes");
static bool ready;
static esp_netif_t *ap;
esp_err_t wifi_manager_init(void) {
    esp_err_t err = nvs_flash_init();
    if (err != ESP_OK) return err;
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ap = esp_netif_create_default_wifi_ap();
    if (!ap) return ESP_ERR_NO_MEM;
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    wifi_config_t config = {0};
    memcpy(config.ap.ssid, CONFIG_BRIDGE_AP_SSID, strlen(CONFIG_BRIDGE_AP_SSID));
    config.ap.ssid_len = strlen(CONFIG_BRIDGE_AP_SSID);
    memcpy(config.ap.password, CONFIG_BRIDGE_AP_PASSWORD, strlen(CONFIG_BRIDGE_AP_PASSWORD));
    config.ap.channel = 6;
    config.ap.max_connection = 1;
    config.ap.authmode = WIFI_AUTH_WPA2_PSK;
    config.ap.pmf_cfg.capable = true;
    config.ap.pmf_cfg.required = true;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ready = true;
    return ESP_OK;
}
bool wifi_manager_is_connected(void) { return ready; }
esp_err_t wifi_manager_get_ip(char *buf, size_t len) {
    if (!ready) return ESP_ERR_INVALID_STATE;
    esp_netif_ip_info_t info;
    esp_err_t err = esp_netif_get_ip_info(ap, &info);
    if (err == ESP_OK) snprintf(buf, len, IPSTR, IP2STR(&info.ip));
    return err;
}
esp_err_t wifi_manager_reset_credentials(void) { return ESP_ERR_NOT_SUPPORTED; }
