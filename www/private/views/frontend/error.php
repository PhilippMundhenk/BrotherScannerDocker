<?php 
include('config.php');
require_once('helper.php');

?>
<!DOCTYPE html>
<html>

<head>
    <?php include('views/frontend/common-head.php'); ?>
    <title><?php echo($page_title); ?></title>
</head>

<body>

    <nav class="navbar navbar-expand-sm fixed-top  navbar-dark bg-dark">
        <div class="container pe-0">
            <a class="navbar-brand" href="/"><?php echo($MODEL); ?></a>
        </div>
    </nav>
    <section class="pt-5 pb-5 mt-0 align-items-center d-flex bg-dark" style="min-height: 100vh; ">
        <div class="container">
            <div class="row  justify-content-center align-items-center d-flex-row text-center h-100">
                <div class="col-12 col-md-8  h-50 ">
                    <span id="status-image" class="d-block mx-auto rounded-circle img-fluid text-white"> <i
                            class="far fa-sad-tear fa-fw fa-10x"></i></span>
                    <h1 class="   text-light mb-2 mt-5"><strong><?php echo($http_code); ?></strong> </h1>
                    <p class="lead  text-light mb-5" id="status-text"><?php echo($page_message); ?></p>


                </div>
            </div>
        </div>
    </section>




    <?php include('views/frontend/common-javascript.php'); ?>



</body>

</html>