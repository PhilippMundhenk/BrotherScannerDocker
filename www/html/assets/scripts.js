function set_state_idle() {
    $('#status-image').html('<i class="far fa-smile fa-fw fa-10x"></i>');
    $('#status-text').text('Ready to scan');
    $('.trigger-scan').removeClass('disabled');
}

function set_state_waiting() {
    $('#status-image').html('<i class="fas fa-hourglass-half fa-fw fa-10x"></i>');
    $('#status-text').text('Waiting for rear pages');
    $('.trigger-scan').removeClass('disabled');
}

function set_state_scan() {
    let spinnerimage = '<i class="fas fa-spinner fa-spin fa-fw fa-10x"></i>';
    if (spinnerimage != $('#status-image').html()) {
        $('#status-image').html(spinnerimage);
    }
    $('#status-text').text('Scan in progress');
    $('.trigger-scan').addClass('disabled');
}

function set_state_ocr() {
    $('#status-image').html('<i class="fas fa-brain fa-fw fa-10x"></i>');
    $('#status-text').text('OCR in progress');
    $('.trigger-scan').removeClass('disabled');
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

function load_files_offcanvas(){
    $.ajax({
        url: '/list-files',
        method: 'GET',
        success: function(response) {
            // Populate the Offcanvas with the response content
            $('#offcanvasContent').html(response);
            
        },
        error: function(xhr, status, error) {
            console.error('Failed to load content:', error);
        }
    });
}

$(document).ready(function() {


    $('.trigger-scan').click(function() {
        var target = $(this).data('trigger');
        console.log('Triggered click event on element with class "trigger-scan" and data-trigger "' + target + '"');
        $.post('/api/scanner/scanto', {
            target: target
        }, function(data) {
            console.log(data);
            $(this).blur();
            
        });
    });


    setInterval(function() {
        $.get('/api/scanner/status', function(data) {


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



    $('#triggerFiles').on('click', function(e) {
        e.preventDefault();
        load_files_offcanvas();
        var offcanvas = new bootstrap.Offcanvas($('#offcanvasFiles')[0]);
        offcanvas.show();
        
    });




});

function toggle_file_rename(source_element){
    var parentDiv = source_element.closest('.list-group-item');
    var parentId = parentDiv.attr('id');

    
    $("#"+parentId+" .file-info-label-default").toggleClass('d-none');
    $("#"+parentId+" .file-info-label-rename").toggleClass('d-none');
    
    $("#"+parentId+" .file-name").toggleClass('d-none');
    $("#"+parentId+" .file-name-new").toggleClass('d-none');
    
    $("#"+parentId+" .file-buttons-default").toggleClass('d-none');
    $("#"+parentId+" .file-buttons-rename").toggleClass('d-none');

    $("#"+parentId+" .file-rename-prefix-date").checked = true;
}

function toggle_file_delete(source_element){
    var parentDiv = source_element.closest('.list-group-item');
    var parentId = parentDiv.attr('id');


    $("#"+parentId+" .file-info-label-default").toggleClass('d-none');
    $("#"+parentId+" .file-info-label-delete").toggleClass('d-none');
    
    $("#"+parentId+" .file-buttons-default").toggleClass('d-none');
    $("#"+parentId+" .file-buttons-delete").toggleClass('d-none');
}


function toggle_file_error(parentId, message){

    $('#'+parentId).addClass('bg-danger text-white');

    var html =` <div class="m-0 d-flex w-100 align-items-center justify-content-between m-0 py-4">
                    <strong class="fs-4 fw-bolder">`+message+`</strong>
                    <small><button type="button" class="btn btn-dark refresh-files m-0 me-2">OK</button></small>
                </div>`;
    $('#'+parentId).html(html);

}   


function toggle_file_success(parentId, message){

    $('#'+parentId).addClass('bg-success text-white');

    var html =` <div class="m-0 d-flex w-100 align-items-center justify-content-between m-0 py-4">
                    <strong class="fs-4 fw-bolder">`+message+`</strong>
                    <small><button type="button" class="btn btn-dark refresh-files m-0 me-2">OK</button></small>
                </div>`;
    $('#'+parentId).html(html);

}   


$(document).on("click", ".refresh-files", function (e) {
    e.preventDefault();
    load_files_offcanvas();

});


$(document).on("click", ".file-rename", function (e) {
    e.preventDefault();
    toggle_file_rename($(this));

});

$(document).on("click", ".file-rename-confirm", function (e) {
    e.preventDefault();
    url = $(this).attr('href');
    var parentDiv = $(this).closest('.list-group-item');
    var parentId = parentDiv.attr('id');

    var filename = $("#"+parentId+" .file-name-original").val();
    var new_filename = $("#"+parentId+" .file-name-new").val();


    var new_filename_prefix = 'none';

    if($("#"+parentId+" .file-rename-prefix-none").is(':checked')) { 
        new_filename_prefix = 'none';
    }
    if($("#"+parentId+" .file-rename-prefix-date").is(':checked')) { 
        new_filename_prefix = 'date';
    }
    if($("#"+parentId+" .file-rename-prefix-datetime").is(':checked')) {
        new_filename_prefix = 'datetime';
    }

    
    console.log('url: '+url);
    console.log('filename: '+filename);
    console.log('new_filename: '+new_filename);
    console.log('new_filename_prefix: '+new_filename_prefix); 


    if (new_filename == '' && new_filename_prefix == 'none') {
        alert('Please enter a new filename or select a prefix');
    }else{


       payload = {
            'new_filename': new_filename,
            'new_filename_prefix': new_filename_prefix
        };
        console.log(payload);
        $.ajax({
            url: url,
            type: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify(payload),
            success: function(response) {
                
                console.log(response);
                console.log('File renamed');
                toggle_file_rename($(this));
                load_files_offcanvas();
            },
            error: function(xhr, status, error) {

                console.log('File NOT renamed');
                toggle_file_error(parentId, 'Rename failed');
            }
        });
        
    }

      


    
});

$(document).on("click", ".file-rename-cancel", function (e) {
    e.preventDefault();
    toggle_file_rename($(this));
});



$(document).on("click", ".file-delete", function (e) {
    e.preventDefault();
    toggle_file_delete($(this));
});

$(document).on("click", ".file-delete-confirm", function (e) {
    e.preventDefault();
    var parentDiv = $(this).closest('.list-group-item');
    var parentId = parentDiv.attr('id');

    url = $(this).attr('href');
    $.ajax({
        url: url,
        type: 'DELETE',
        success: function(response) {
            toggle_file_success(parentId, 'File deleted');
            setTimeout(() => {
                load_files_offcanvas();
            }, 500);
            
            
        },
        error: function(response, xhr, status, error) {
            toggle_file_error(parentId, 'Delete failed');
        }
    });
    
});

$(document).on("click", ".file-delete-cancel", function (e) {
    e.preventDefault();
    toggle_file_delete($(this));
});



//document.addEventListener('DOMContentLoaded', function () {
//    var offcanvasElement = document.getElementById('offcanvasExample');
//    offcanvasElement.addEventListener('shown.bs.offcanvas', function () {
//        // Trigger any necessary initialization here
//        // For example, you can reinitialize the radio buttons or any other components
//        console.log('Offcanvas is shown');
//    });
//});
