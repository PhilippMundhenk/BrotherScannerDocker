<?php

$timezone = getenv('TZ');
if ($timezone === false) {
    $timezone = 'UTC';
}
date_default_timezone_set($timezone);

echo "Timezone: " . date_default_timezone_get();
echo "<br>";
echo "Time: " . date("Y-m-d H:i:s");
?>