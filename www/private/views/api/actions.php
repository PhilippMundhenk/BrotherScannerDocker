<?php
include('config.php');
require_once('helper.php');

// GET /api/actions: the scan actions this container offers, with their labels
// (RENAME_GUI_*), whether they are enabled (DISABLE_GUI_*), what they do, and
// the parameters a trigger accepts.

function action_entry($target, $default_label, $description, $rename_var, $disable_var) {
        global $$rename_var, $$disable_var;
        $label = (isset($$rename_var) && $$rename_var) ? $$rename_var : $default_label;
        $enabled = !(isset($$disable_var) && $$disable_var);
        return array(
                'target' => $target,
                'label' => $label,
                'enabled' => $enabled,
                'description' => $description,
                'trigger' => array(
                        'post' => '/api/scanner/scanto (form field target=' . $target . ')',
                        'get' => '/api/scanner/scanto/' . $target,
                ),
        );
}

$defaults = array(
        'resolution' => isset($RESOLUTION) && $RESOLUTION !== '' ? (int)$RESOLUTION : 300,
        'mode' => isset($SCAN_MODE) && $SCAN_MODE !== '' ? $SCAN_MODE : null,
        'source' => isset($SCAN_SOURCE) && $SCAN_SOURCE !== '' ? $SCAN_SOURCE : null,
);

json(array(
        'api_version' => 1,
        'version' => container_version(),
        'device' => array(
                'name' => isset($NAME) && $NAME !== '' ? $NAME : 'Scanner',
                'model' => isset($MODEL) && $MODEL !== '' ? $MODEL : null,
                'host' => isset($IPADDRESS) && $IPADDRESS !== '' ? $IPADDRESS : null,
                'capabilities' => device_capabilities(),
        ),
        'actions' => array(
                action_entry('file', 'Scan to file',
                        'Scans the front pages, waits REAR_PAGE_WAIT_SECONDS for a rear scan, converts to PDF and runs the post-processing.',
                        'RENAME_GUI_SCANTOFILE', 'DISABLE_GUI_SCANTOFILE'),
                action_entry('email', 'Scan to email',
                        'Scans the rear pages of the job waiting for them and merges both sides into one PDF (POST /api/jobs/<id>/rear addresses a specific job).',
                        'RENAME_GUI_SCANTOEMAIL', 'DISABLE_GUI_SCANTOEMAIL'),
                action_entry('ocr', 'Scan to OCR',
                        'Like scan to file, in gray mode.',
                        'RENAME_GUI_SCANTOOCR', 'DISABLE_GUI_SCANTOOCR'),
                action_entry('image', 'Scan to image',
                        'Placeholder, only logs that it is not implemented; mount your own script to use it.',
                        'RENAME_GUI_SCANTOIMAGE', 'DISABLE_GUI_SCANTOIMAGE'),
        ),
        'parameters' => array(
                'resolution' => array('type' => 'integer', 'unit' => 'dpi', 'default' => $defaults['resolution'],
                        'description' => 'Scan resolution; one of the values the device lists at startup'),
                'mode' => array('type' => 'string', 'default' => $defaults['mode'],
                        'description' => 'Scan mode as listed by the device, e.g. "True Gray" or "Black & White"'),
                'source' => array('type' => 'string', 'default' => $defaults['source'],
                        'description' => 'Paper source as listed by the device, e.g. "FlatBed" or a duplex ADF'),
                'wait' => array('type' => 'boolean', 'default' => false,
                        'description' => 'POST only: wait for the scan script to finish before answering'),
        ),
        'jobs' => array(
                'list' => '/api/jobs',
                'detail' => '/api/jobs/<id>',
                'rear' => '/api/jobs/<id>/rear (POST)',
        ),
        'authentication' => isset($API_TOKEN) && $API_TOKEN !== '' ? 'token required for triggers (Authorization: Bearer or X-API-Token)' : 'none',
));
?>
