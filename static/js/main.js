// Main JavaScript for Bite Me Buddy

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});

// Cart management functions
const CartManager = {
    addItem: function(itemId, quantity = 1) {
        let cart = JSON.parse(localStorage.getItem('bite_me_buddy_cart') || '{}');
        cart[itemId] = (cart[itemId] || 0) + quantity;
        localStorage.setItem('bite_me_buddy_cart', JSON.stringify(cart));
        this.updateCartCount();
        return cart;
    },
    
    removeItem: function(itemId) {
        let cart = JSON.parse(localStorage.getItem('bite_me_buddy_cart') || '{}');
        delete cart[itemId];
        localStorage.setItem('bite_me_buddy_cart', JSON.stringify(cart));
        this.updateCartCount();
        return cart;
    },
    
    updateQuantity: function(itemId, quantity) {
        let cart = JSON.parse(localStorage.getItem('bite_me_buddy_cart') || '{}');
        if (quantity <= 0) {
            delete cart[itemId];
        } else {
            cart[itemId] = quantity;
        }
        localStorage.setItem('bite_me_buddy_cart', JSON.stringify(cart));
        this.updateCartCount();
        return cart;
    },
    
    getCart: function() {
        return JSON.parse(localStorage.getItem('bite_me_buddy_cart') || '{}');
    },
    
    clearCart: function() {
        localStorage.removeItem('bite_me_buddy_cart');
        this.updateCartCount();
    },
    
    updateCartCount: function() {
        const cart = this.getCart();
        const count = Object.values(cart).reduce((a, b) => a + b, 0);
        const countElements = document.querySelectorAll('.cart-count');
        countElements.forEach(el => {
            el.textContent = count;
            el.style.display = count > 0 ? 'inline' : 'none';
        });
    },
    
    getCartTotal: async function() {
        const cart = this.getCart();
        let total = 0;
        
        // Fetch item prices and calculate total
        for (const [itemId, quantity] of Object.entries(cart)) {
            try {
                const response = await fetch(`/api/menu-items/${itemId}/price`);
                if (response.ok) {
                    const data = await response.json();
                    total += data.price * quantity;
                }
            } catch (error) {
                console.error('Error fetching item price:', error);
            }
        }
        
        return total;
    }
};

// Initialize cart count on page load
document.addEventListener('DOMContentLoaded', function() {
    CartManager.updateCartCount();
});

// Form validation helper
const FormValidator = {
    validateEmail: function(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },
    
    validatePhone: function(phone) {
        const re = /^[0-9]{10}$/;
        return re.test(phone.replace(/\D/g, ''));
    },
    
    validatePassword: function(password) {
        return password.length >= 6;
    },
    
    showError: function(input, message) {
        const formGroup = input.closest('.form-group') || input.parentElement;
        let errorElement = formGroup.querySelector('.invalid-feedback');
        
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.className = 'invalid-feedback';
            formGroup.appendChild(errorElement);
        }
        
        errorElement.textContent = message;
        input.classList.add('is-invalid');
    },
    
    clearError: function(input) {
        input.classList.remove('is-invalid');
    },
    
    validateForm: function(form) {
        let isValid = true;
        const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
        
        inputs.forEach(input => {
            if (!input.value.trim()) {
                this.showError(input, 'This field is required');
                isValid = false;
            } else {
                this.clearError(input);
                
                // Additional validation based on input type
                if (input.type === 'email' && !this.validateEmail(input.value)) {
                    this.showError(input, 'Please enter a valid email address');
                    isValid = false;
                }
                
                if (input.type === 'tel' && !this.validatePhone(input.value)) {
                    this.showError(input, 'Please enter a valid 10-digit phone number');
                    isValid = false;
                }
                
                if (input.type === 'password' && !this.validatePassword(input.value)) {
                    this.showError(input, 'Password must be at least 6 characters');
                    isValid = false;
                }
            }
        });
        
        return isValid;
    }
};

// Toast notifications
const Toast = {
    show: function(message, type = 'info', duration = 3000) {
        // Create toast container if it doesn't exist
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                max-width: 350px;
            `;
            document.body.appendChild(container);
        }
        
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast show align-items-center text-white bg-${type} border-0`;
        toast.style.cssText = 'margin-bottom: 10px;';
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        container.appendChild(toast);
        
        // Auto remove after duration
        setTimeout(() => {
            toast.remove();
        }, duration);
        
        // Add click to dismiss
        toast.querySelector('.btn-close').addEventListener('click', () => {
            toast.remove();
        });
    }
};

// Handle HTMX events
document.addEventListener('htmx:beforeRequest', function(e) {
    // Show loading indicator
    const target = e.detail.target;
    if (target) {
        target.classList.add('htmx-request');
    }
});

document.addEventListener('htmx:afterRequest', function(e) {
    // Hide loading indicator
    const target = e.detail.target;
    if (target) {
        target.classList.remove('htmx-request');
    }
});

document.addEventListener('htmx:responseError', function(e) {
    Toast.show('An error occurred. Please try again.', 'danger');
});

// Mobile menu toggle enhancement
document.addEventListener('DOMContentLoaded', function() {
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    
    if (navbarToggler && navbarCollapse) {
        navbarToggler.addEventListener('click', function() {
            navbarCollapse.classList.toggle('show');
        });
        
        // Close menu when clicking outside on mobile
        document.addEventListener('click', function(event) {
            if (window.innerWidth <= 992 && 
                !navbarToggler.contains(event.target) && 
                !navbarCollapse.contains(event.target) &&
                navbarCollapse.classList.contains('show')) {
                navbarCollapse.classList.remove('show');
            }
        });
    }
});

// Smooth scroll to top
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// Back to top button
document.addEventListener('DOMContentLoaded', function() {
    const backToTopButton = document.createElement('button');
    backToTopButton.innerHTML = '<i class="fas fa-chevron-up"></i>';
    backToTopButton.className = 'btn btn-primary rounded-circle';
    backToTopButton.style.cssText = `
        position: fixed;
        bottom: 80px;
        right: 20px;
        width: 50px;
        height: 50px;
        z-index: 1000;
        display: none;
    `;
    backToTopButton.addEventListener('click', scrollToTop);
    document.body.appendChild(backToTopButton);
    
    // Show/hide button based on scroll position
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTopButton.style.display = 'block';
        } else {
            backToTopButton.style.display = 'none';
        }
    });
});

// Network status detection
window.addEventListener('online', function() {
    Toast.show('You are back online', 'success');
});

window.addEventListener('offline', function() {
    Toast.show('You are offline. Some features may not work.', 'warning');
});
