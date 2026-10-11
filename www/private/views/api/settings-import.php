<?php
include('config.php');
require_once('helper.php');
require_once('settings.php');

// POST /api/settings/import-environment: copy every setting the environment
// sets into the configuration file (migration to file-managed settings, #161).
// The environment keeps winning until its entries are removed from the compose
// file and the container restarted. Needs ALLOW_GUI_SETTINGS=true and the API
// token when one is configured (checked by the route).

if (!settings_enabled()) {
    send_json_error(403, 'Settings are disabled (set ALLOW_GUI_SETTINGS=true)');
}
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    send_json_error(405, 'Method not allowed');
}

$result = settings_import_environment();
if ($result['error'] !== null) {
    send_json_error(500, $result['error']);
}
$result['config_file'] = settings_config_path();
$result['message'] = empty($result['environment'])
    ? 'No setting comes from the environment; nothing to copy'
    : 'The environment still wins: remove these entries from the compose file and restart the container to manage them in the file';
$result['settings'] = settings_all();
json($result);
?>
