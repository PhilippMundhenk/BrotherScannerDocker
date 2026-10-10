<?php
include('config.php');
require_once('helper.php');
require_once('settings.php');

// GET /api/settings  -> every setting with value, source (environment|file|default), locked, restart
// PUT /api/settings  -> JSON object {KEY: value, ...}; empty value removes the key from the file
// Both need ALLOW_GUI_SETTINGS=true; PUT also needs the API token when one is configured.

if (!settings_enabled()) {
    send_json_error(403, 'Settings are disabled (set ALLOW_GUI_SETTINGS=true)');
}

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    json(array(
        'config_file' => settings_config_path(),
        'config_file_exists' => is_file(settings_config_path()),
        'settings' => settings_all(),
    ));
}

if ($_SERVER['REQUEST_METHOD'] === 'PUT' || $_SERVER['REQUEST_METHOD'] === 'POST') {
    $raw = file_get_contents('php://input');
    $changes = json_decode($raw, true);
    if (!is_array($changes)) {
        send_json_error(400, 'Body must be a JSON object of setting names and values');
    }
    $result = settings_save($changes);
    if (!empty($result['errors'])) {
        header('Content-Type: application/json');
        http_response_code(400);
        json(array('code' => 400, 'message' => 'Invalid settings', 'errors' => $result['errors']));
    }
    $result['settings'] = settings_all();
    json($result);
}

send_json_error(405, 'Method not allowed');
?>
