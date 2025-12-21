// Bite Me Buddy - Clock and Secret Admin Access Logic
// MODIFIED: Only 15 second long press required (no taps)

class SecretClock {
    constructor() {
        this.pressTimer = null;
        this.pressStartTime = null;
        this.isEditMode = false;
        
        this.initialize();
    }
    
    initialize() {
        // Update clock immediately and then every second
        this.updateClock();
        setInterval(() => this.updateClock(), 1000);
        
        // Setup event listeners for secret access
        this.setupSecretAccess();
        
        // Setup edit mode handlers
        this.setupEditMode();
    }
    
    updateClock() {
        const now = new Date();
        
        // Convert to IST (UTC+5:30)
        const istOffset = 5.5 * 60 * 60 * 1000;
        const istTime = new Date(now.getTime() + istOffset);
        
        let hours = istTime.getUTCHours();
        const minutes = istTime.getUTCMinutes().toString().padStart(2, '0');
        const seconds = istTime.getUTCSeconds().toString().padStart(2, '0');
        
        // Convert to 12-hour format
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12;
        hours = hours ? hours : 12; // Convert 0 to 12
        
        const timeString = `${hours.toString().padStart(2, '0')}:${minutes}:${seconds} ${ampm}`;
        
        const clockElement = document.getElementById('digitalClock');
        if (clockElement && !this.isEditMode) {
            clockElement.textContent = timeString;
        }
    }
    
    setupSecretAccess() {
        const clockContainer = document.getElementById('clockContainer');
        if (!clockContainer) return;
        
        // Mouse events
        clockContainer.addEventListener('mousedown', () => this.startPressTimer());
        clockContainer.addEventListener('mouseup', () => this.cancelPressTimer());
        clockContainer.addEventListener('mouseleave', () => this.cancelPressTimer());
        
        // Touch events for mobile
        clockContainer.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this.startPressTimer();
        });
        
        clockContainer.addEventListener('touchend', (e) => {
            e.preventDefault();
            this.cancelPressTimer();
        });
        
        clockContainer.addEventListener('touchcancel', () => this.cancelPressTimer());
    }
    
    startPressTimer() {
        this.pressStartTime = Date.now();
        
        // Long press detection (15 seconds) - MODIFIED: Direct edit mode
        this.pressTimer = setTimeout(() => {
            console.log('Long press detected (15 seconds) - Entering edit mode');
            this.enterEditMode();
            
        }, 15000);
    }
    
    cancelPressTimer() {
        if (this.pressTimer) {
            clearTimeout(this.pressTimer);
            this.pressTimer = null;
        }
    }
    
    enterEditMode() {
        this.isEditMode = true;
        
        const clockElement = document.getElementById('digitalClock');
        const editElement = document.getElementById('clockEdit');
        
        if (clockElement && editElement) {
            clockElement.style.display = 'none';
            editElement.style.display = 'block';
            
            // Set current time in edit fields
            const now = new Date();
            const istOffset = 5.5 * 60 * 60 * 1000;
            const istTime = new Date(now.getTime() + istOffset);
            
            let hours = istTime.getUTCHours();
            const minutes = istTime.getUTCMinutes();
            const ampm = hours >= 12 ? 'PM' : 'AM';
            
            hours = hours % 12;
            hours = hours ? hours : 12;
            
            document.getElementById('editHour').value = hours;
            document.getElementById('editMinute').value = minutes;
            document.getElementById('editAmPm').value = ampm;
        }
    }
    
    exitEditMode() {
        this.isEditMode = false;
        
        const clockElement = document.getElementById('digitalClock');
        const editElement = document.getElementById('clockEdit');
        
        if (clockElement && editElement) {
            clockElement.style.display = 'block';
            editElement.style.display = 'none';
        }
    }
    
    setupEditMode() {
        // Save button handler
        window.saveClockTime = () => {
            const hour = parseInt(document.getElementById('editHour').value);
            const minute = parseInt(document.getElementById('editMinute').value);
            const ampm = document.getElementById('editAmPm').value;
            
            if (!hour || hour < 1 || hour > 12) {
                this.showMessage('Please enter a valid hour (1-12)', 'error');
                return;
            }
            
            if (!minute || minute < 0 || minute > 59) {
                this.showMessage('Please enter valid minutes (0-59)', 'error');
                return;
            }
            
            // Check for secret combination 3:43
            if (hour === 3 && minute === 43) {
                console.log('Secret combination 3:43 detected - redirecting to admin login');
                window.location.href = '/admin-login';
            } else {
                this.exitEditMode();
                this.showMessage('Time saved', 'info');
            }
        };
        
        // Cancel button handler
        window.cancelClockEdit = () => {
            this.exitEditMode();
        };
    }
    
    showMessage(message, type) {
        // Create a temporary message element
        const messageDiv = document.createElement('div');
        messageDiv.className = `alert alert-${type === 'error' ? 'danger' : type} position-fixed`;
        messageDiv.style.cssText = `
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
            animation: slideIn 0.3s ease-out;
        `;
        messageDiv.textContent = message;
        
        document.body.appendChild(messageDiv);
        
        // Remove after 3 seconds
        setTimeout(() => {
            messageDiv.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 300);
        }, 3000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new SecretClock();
});

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);