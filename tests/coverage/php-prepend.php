<?php
// Prepended to every PHP request in the coverage image: collect the executed
// lines with pcov and dump them at shutdown (one small JSON file per request).
if (function_exists('pcov\\start')) {
    \pcov\start();
    register_shutdown_function(function () {
        \pcov\stop();
        $data = \pcov\collect(\pcov\inclusive, array());
        $out = array();
        foreach ($data as $file => $lines) {
            if (strpos($file, '/var/www/') !== 0 || strpos($file, 'coverage-prepend') !== false) {
                continue;
            }
            $out[$file] = $lines;
        }
        @file_put_contents('/var/www/coverage/' . uniqid('req_', true) . '.json', json_encode($out));
    });
}
