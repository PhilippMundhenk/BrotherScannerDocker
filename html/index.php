<?php 
include 'config.php'; 

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
    <meta charset="UTF-8">
    <title>Brother <?php echo($MODEL); ?></title>

    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <meta name="description" content="">
    <meta name="author" content="">
    <link rel="icon" href="favicon.ico">
    <link rel="stylesheet" href=" https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css ">
    <link rel="stylesheet" href="https://use.fontawesome.com/releases/v5.2.0/css/all.css">
    <!-- Plugins -->
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


    <div class="offcanvas offcanvas-start" tabindex="-1" id="offcanvasFiles" aria-labelledby="offcanvasFilesLabel">
	
        <div class="offcanvas-header">
            <h5 class="offcanvas-title" id="offcanvasFilesLabel">Last scanned</h5>
            <button type="button" class="btn-close text-reset" data-bs-dismiss="offcanvas" aria-label="Close"></button>
        </div>
        <div class="offcanvas-body m-0 p-0" id="offcanvasContent">





        </div>
    </div>

    <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-ka7Sk0Gln4gmtz2MlQnikT1wXgYsOg+OMhuP+IlRH9sENBO0LRn5q+8nbTov4+1p" crossorigin="anonymous">
    </script>


    <script>
    function set_state_idle() {
        $('#status-image').html('<i class="far fa-smile fa-fw fa-10x"></i>');
        $('#status-text').text('Ready to scan');
    }

    function set_state_waiting() {
        $('#status-image').html('<i class="fas fa-hourglass-half fa-fw fa-10x"></i>');
        $('#status-text').text('Waiting for rear pages');
    }

    function set_state_scan() {
        let spinnerimage = '<i class="fas fa-spinner fa-spin fa-fw fa-10x"></i>';
        if (spinnerimage != $('#status-image').html()) {
            $('#status-image').html(spinnerimage);
        }
        $('#status-text').text('Scan in progress');
    }

    function set_state_ocr() {
        $('#status-image').html('<i class="fas fa-brain fa-fw fa-10x"></i>');
        $('#status-text').text('OCR in progress');
    }

    function set_state(state) {
        switch (state) {
            case 'idle':
                set_state_idle();
                break;
            case 'waiting':
                set_state_waiting();
                break;
            case 'scan':
                set_state_scan();
                break;
            case 'ocr':
                set_state_ocr();
                break;
            default:
                set_state_idle();
        }
    }

    $(document).ready(function() {

        $('.trigger-scan').click(function() {
            var target = $(this).data('trigger');
            $.post('/scan.php', {
                target: target
            }, function(data) {
                console.log(data);
            });
        });

        // listen to action.php for status changes
        setInterval(function() {
            $.get('/active.php', function(data) {


                let state = 'idle';

                if (data.ocr && data.waiting && !data.scan) {
                    state = 'ocr';
                } else if (data.scan && data.waiting) {
                    state = 'scan';
                } else if (data.scan) {
                    state = 'scan';
                } else if (data.ocr && !data.scan) {
                    state = 'ocr';
                } else if (!data.ocr && !data.scan && data.waiting) {
                    state = 'waiting';
                } else if (!data.ocr && !data.scan && !data.waiting) {
                    state = 'idle';
                }
                set_state(state);
            });
        }, 1000);

    });



    $(document).ready(function() {

        $('#triggerFiles').on('click', function(e) {
            e.preventDefault();
            $.ajax({
                url: '/list.php',
                method: 'GET',
                success: function(response) {
                    // Populate the Offcanvas with the response content
                    $('#offcanvasContent').html(response);

                    // Show the Offcanvas
                    var offcanvas = new bootstrap.Offcanvas($('#offcanvasFiles')[0]);
                    offcanvas.show();
                },
                error: function(xhr, status, error) {
                    console.error('Failed to load content:', error);
                }
            });
        });
    });
    </script>


</body>

</html>