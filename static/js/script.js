// script.js
document.addEventListener('DOMContentLoaded', function() {
    // Konfirmasi hapus dengan sweet alert style (opsional)
    const deleteLinks = document.querySelectorAll('.delete-confirm');
    deleteLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            if (!confirm('Apakah Anda yakin ingin menghapus? Data yang dihapus tidak dapat dikembalikan.')) {
                e.preventDefault();
            }
        });
    });

    // Tooltip Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto hide alert setelah 5 detik
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            bootstrap.Alert.getOrCreateInstance(alert).close();
        });
    }, 5000);

    // Smooth scroll untuk anchor
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Tambahkan class loading saat submit form (opsional)
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
                submitBtn.disabled = true;
            }
        });
    });

    // Register Service Worker for PWA
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(registration => {
                console.log('Service Worker registered with scope:', registration.scope);
            })
            .catch(error => {
                console.log('Service Worker registration failed:', error);
            });
    }

    // Rupiah Currency Formatting for Amount Inputs
    initializeRupiahFormatting();
});

/**
 * New input-masking approach for Rupiah currency formatting
 * This approach prevents cursor jumping and maintains proper digit order
 */
function formatRupiah(input) {
    // Save cursor position relative to digits only
    const cursorPos = input.selectionStart;
    const oldValue = input.value;
    
    // Count digits before cursor in old value
    const digitsBeforeCursor = oldValue.slice(0, cursorPos).replace(/\D/g, '').length;
    
    // Strip everything except digits
    const digits = oldValue.replace(/\D/g, '');
    
    // Limit to reasonable max (15 digits)
    const limitedDigits = digits.slice(0, 15);
    
    // Format with dot thousand separator
    const formatted = limitedDigits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    
    // Update display value
    input.value = formatted;
    
    // Update hidden input with raw number for form submission
    const hiddenInput = input.previousElementSibling || document.querySelector('input[name="amount_raw"]');
    if (hiddenInput && hiddenInput.type === 'hidden') {
        hiddenInput.value = limitedDigits;
    }
    
    // Restore cursor: count forward through formatted string until we've
    // passed digitsBeforeCursor digits
    let digitCount = 0;
    let newCursorPos = 0;
    for (let i = 0; i < formatted.length; i++) {
        if (/\d/.test(formatted[i])) digitCount++;
        if (digitCount === digitsBeforeCursor) {
            newCursorPos = i + 1;
            break;
        }
    }
    // If cursor was at end or past all digits
    if (digitsBeforeCursor === 0) newCursorPos = 0;
    if (digitCount < digitsBeforeCursor) newCursorPos = formatted.length;
    
    input.setSelectionRange(newCursorPos, newCursorPos);
}

/**
 * Initialize Rupiah currency formatting using event delegation
 */
function initializeRupiahFormatting() {
    // Use event delegation to handle all amount inputs
    document.addEventListener('input', function(e) {
        if (e.target.matches('input[data-rupiah]')) {
            formatRupiah(e.target);
        }
    });
}
