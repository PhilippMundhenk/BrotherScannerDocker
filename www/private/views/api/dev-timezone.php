<?php
include('config.php');
require_once('helper.php');

json(
    array(
        'timezone' => date_default_timezone_get(),
        'time' => date("Y-m-d H:i:s")
    )
);

?>