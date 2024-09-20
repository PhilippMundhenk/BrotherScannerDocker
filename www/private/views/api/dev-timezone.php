<?php
include('config.php');
require_once('helper.php');

$timezone_data = array(
    'timezone' => date_default_timezone_get(),
    'datetime' => date("Y-m-d H:i:s")
);

json($timezone_data);

?>