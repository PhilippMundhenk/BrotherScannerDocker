<?php
include('config.php');
require_once('helper.php');

$timezone_data = array(
    'timezone' => date_default_timezone_get(),
    'datetime' => date("Y-m-d H:i:s")
);
trigger_error("Timezone: ".$timezone_data['timezone'] . " DateTime: ".$timezone_data['datetime'], E_API);
json($timezone_data);

?>