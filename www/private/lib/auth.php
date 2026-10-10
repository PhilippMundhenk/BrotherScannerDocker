<?php
// Optional API token (API_TOKEN) for everything that starts a scan or changes a file.

function api_token_required() {
    global $API_TOKEN;
    if (!isset($API_TOKEN) || $API_TOKEN === '') {
        return;
    }
    $provided = '';
    $auth = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
    if (stripos($auth, 'Bearer ') === 0) {
        $provided = trim(substr($auth, 7));
    } elseif (isset($_SERVER['HTTP_X_API_TOKEN'])) {
        $provided = $_SERVER['HTTP_X_API_TOKEN'];
    } elseif (isset($_POST['token'])) {
        $provided = $_POST['token'];
    } elseif (isset($_GET['token'])) {
        $provided = $_GET['token'];
    }
    if (!hash_equals($API_TOKEN, (string)$provided)) {
        trigger_error("API request rejected: missing or wrong token from " . ($_SERVER['REMOTE_ADDR'] ?? 'unknown'), E_API);
        send_json_error(401, 'API token required');
    }
}

/** Version string baked into the image (tag, branch-sha or dev). */
