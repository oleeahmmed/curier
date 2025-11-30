(function($) {
    'use strict';
    
    $(document).ready(function() {
        console.log('Shipment autofill script loaded');
        
        // Function to get CSRF token
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
        
        const csrftoken = getCookie('csrftoken');
        
        // Function to autofill sender information
        function autofillSenderInfo(customerId) {
            if (!customerId) {
                console.log('No customer selected');
                return;
            }
            
            console.log('Fetching customer data for ID:', customerId);
            
            // Show loading indicator
            const senderNameField = $('#id_sender_name');
            if (senderNameField.length) {
                senderNameField.css('background-color', '#fffacd');
            }
            
            $.ajax({
                url: '/api/customer/' + customerId + '/',
                type: 'GET',
                headers: {
                    'X-CSRFToken': csrftoken
                },
                success: function(data) {
                    console.log('Customer data received:', data);
                    
                    if (data.success) {
                        // Fill sender fields
                        $('#id_sender_name').val(data.name).css('background-color', '#d4edda');
                        $('#id_sender_phone').val(data.phone).css('background-color', '#d4edda');
                        $('#id_sender_address').val(data.address).css('background-color', '#d4edda');
                        $('#id_sender_country').val(data.country).css('background-color', '#d4edda');
                        
                        // Remove highlight after 2 seconds
                        setTimeout(function() {
                            $('#id_sender_name, #id_sender_phone, #id_sender_address, #id_sender_country')
                                .css('background-color', '');
                        }, 2000);
                        
                        console.log('Sender fields autofilled successfully');
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Error fetching customer data:', error);
                    alert('Error loading customer data. Please try again.');
                    
                    // Remove loading indicator
                    $('#id_sender_name').css('background-color', '');
                }
            });
        }
        
        // Watch for customer selection changes
        // Handle both regular select and Django autocomplete widget
        
        // For Django autocomplete widget (select2)
        $(document).on('change', '#id_customer', function() {
            const customerId = $(this).val();
            console.log('Customer changed (autocomplete):', customerId);
            if (customerId) {
                autofillSenderInfo(customerId);
            }
        });
        
        // For regular select dropdown (fallback)
        $('#id_customer').on('change', function() {
            const customerId = $(this).val();
            console.log('Customer changed (select):', customerId);
            if (customerId) {
                autofillSenderInfo(customerId);
            }
        });
        
        // Also trigger on page load if customer is already selected
        setTimeout(function() {
            const customerId = $('#id_customer').val();
            if (customerId) {
                console.log('Customer already selected on page load:', customerId);
                // Don't autofill on edit, only on add
                const isAddPage = window.location.pathname.includes('/add/');
                if (isAddPage) {
                    autofillSenderInfo(customerId);
                }
            }
        }, 500);
        
        console.log('Shipment autofill handlers registered');
    });
})(django.jQuery);
