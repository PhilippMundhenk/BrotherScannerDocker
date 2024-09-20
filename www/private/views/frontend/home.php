<?php 
include('config.php');
require_once('helper.php');

if (isset($RENAME_GUI_SCANTOFILE) && $RENAME_GUI_SCANTOFILE) {
    $button_file = $RENAME_GUI_SCANTOFILE;
} else {
    $button_file = "Scan to file";
}
if (isset($RENAME_GUI_SCANTOEMAIL) && $RENAME_GUI_SCANTOEMAIL) {
    $button_email = $RENAME_GUI_SCANTOEMAIL;
} else {
    $button_email = "Scan to email";
}
if (isset($RENAME_GUI_SCANTOIMAGE) && $RENAME_GUI_SCANTOIMAGE) {
    $button_image = $RENAME_GUI_SCANTOIMAGE;
} else {
    $button_image = "Scan to image";
}
if (isset($RENAME_GUI_SCANTOOCR) && $RENAME_GUI_SCANTOOCR) {
    $button_ocr = $RENAME_GUI_SCANTOOCR;
} else {
    $button_ocr = "Scan to OCR";
}
?>
<!DOCTYPE html>
<html>

<head>
    <?php include('views/frontend/common-head.php'); ?>
    <title>Brother <?php echo($MODEL); ?></title>
    <style>
        /* prevent persistent highlight after click to scan */
        .trigger-scan:focus, .trigger-scan:active:focus {
            box-shadow: none !important;
        }
    </style>
</head>

<body>

    <nav class="navbar navbar-expand-sm fixed-top  navbar-dark bg-dark">
        <div class="container pe-0">
            <a class="navbar-brand" href="/"><?php echo($MODEL); ?></a>
            <a class="nav-link text-white me-0" id="triggerFiles" href="#"><i
                    class="far fa-file-pdf  fa-fw fa-2x"></i></a>

        </div>
    </nav>
    <section class="pt-5 pb-5 mt-0 align-items-center d-flex bg-dark" style="min-height: 100vh; ">
        <div class="container">
            <div class="row  justify-content-center align-items-center d-flex-row text-center h-100">
                <div class="col-12 col-md-8  h-50 ">
                    <span id="status-image" class="d-block mx-auto rounded-circle img-fluid text-white"> <i
                            class="far fa-smile fa-fw fa-10x"></i></span>
                    <h1 class="   text-light mb-2 mt-5"><strong><?php echo($MODEL); ?></strong> </h1>
                    <p class="lead  text-light mb-5" id="status-text">Ready to scan</p>

                    <?php 
                if (!isset($DISABLE_GUI_SCANTOFILE) || $DISABLE_GUI_SCANTOFILE != true) {
                    echo('<p><a href="#" class="btn btn-outline-light btn-lg d-block trigger-scan" data-trigger="file">'.$button_file.'</a></p>');
                }
                if (!isset($DISABLE_GUI_SCANTOEMAIL) || $DISABLE_GUI_SCANTOEMAIL != true) {
                    echo('<p><a href="#" class="btn btn-outline-light btn-lg d-block trigger-scan" data-trigger="email">'.$button_email.'</a></p>');
                }
                if (!isset($DISABLE_GUI_SCANTOIMAGE) || $DISABLE_GUI_SCANTOIMAGE != true) {
                    echo('<p><a href="#" class="btn btn-outline-light btn-lg d-block trigger-scan" data-trigger="image">'.$button_image.'</a></p>');
                }
                if (!isset($DISABLE_GUI_SCANTOOCR) || $DISABLE_GUI_SCANTOOCR != true) {
                    echo('<p><a href="#" class="btn btn-outline-light btn-lg d-block trigger-scan" data-trigger="ocr">'.$button_ocr.'</a></p>');
                }
            ?>
                </div>
            </div>
        </div>
    </section>

    <!-- Offcanvas -->
    <div class="offcanvas offcanvas-start" tabindex="-1" id="offcanvasFiles" aria-labelledby="offcanvasFilesLabel">
	
        <div class="offcanvas-header">
            <h5 class="offcanvas-title" id="offcanvasFilesLabel">Last scanned</h5>
            <button type="button" class="btn-close text-reset" data-bs-dismiss="offcanvas" aria-label="Close"></button>
        </div>
        <div class="offcanvas-body m-0 p-0" id="offcanvasContent">





        </div>
    </div>

    <!-- AJAX Modal -->
    <div class="modal" id="ajax_modal" tabindex="-1" aria-labelledby="ajax_modalLabel" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content" id="ajax_modal_content">

            </div>
        </div>
    </div>



    <?php include('views/frontend/common-javascript.php'); ?>


    <script src="/assets/scripts.min.js"></script>


</body>

</html>