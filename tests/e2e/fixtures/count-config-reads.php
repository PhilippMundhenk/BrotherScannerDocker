<?php
// Counts how often the configuration file is opened while the settings page's
// data is built (#196): config.php overlays the file once, then settings_all()
// asks for every setting. Run inside the container: php < count-config-reads.php
// Prints "settings=<n> opens=<n> stats=<n>".
class CountingWrapper {
    public static $opens = 0;
    public static $stats = 0;
    public static $target = '';
    public $context;
    private $handle;

    public static function swap($enable) {
        if ($enable) {
            stream_wrapper_unregister('file');
            stream_wrapper_register('file', __CLASS__);
        } else {
            stream_wrapper_restore('file');
        }
    }

    public function stream_open($path, $mode, $options, &$opened) {
        if (str_contains($path, self::$target)) {
            self::$opens++;
        }
        self::swap(false);
        $this->handle = fopen($path, $mode);
        self::swap(true);
        return $this->handle !== false;
    }
    public function stream_read($count) { return fread($this->handle, $count); }
    public function stream_eof() { return feof($this->handle); }
    public function stream_close() { fclose($this->handle); }
    public function stream_stat() { return fstat($this->handle); }
    public function stream_set_option($option, $arg1, $arg2) { return false; }
    public function url_stat($path, $flags) {
        if (str_contains($path, self::$target)) {
            self::$stats++;
        }
        self::swap(false);
        $result = @stat($path);
        self::swap(true);
        return $result;
    }
}

$conf = sys_get_temp_dir() . '/count-config-reads.conf';
file_put_contents($conf, "SCAN_MODE=True Gray\nREMOVE_BLANK_THRESHOLD=0.5\n");
$SCANNER_CONFIG_FILE = $conf;
set_include_path('/var/www/private/');
require_once 'settings.php';
settings_catalogue();  // loaded before counting starts, like opcache has it in the web server
CountingWrapper::$target = basename($conf);
CountingWrapper::swap(true);
extract(settings_file_overlay(), EXTR_OVERWRITE);  // what config.php does for every view
$all = settings_all();                              // what the settings page and GET /api/settings do
CountingWrapper::swap(false);
unlink($conf);
printf("settings=%d opens=%d stats=%d\n", count($all), CountingWrapper::$opens, CountingWrapper::$stats);
