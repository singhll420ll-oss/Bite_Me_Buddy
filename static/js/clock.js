// Real Time Clock with IST - 15 Second Touch + Time Set for Admin
document.addEventListener('DOMContentLoaded', function() {
    const clockElement = document.getElementById('realTimeClock');
    const clockEdit = document.getElementById('clockEdit');
    const editHour = document.getElementById('editHour');
    const editMinute = document.getElementById('editMinute');
    const editAmPm = document.getElementById('editAmPm');
    const saveBtn = document.getElementById('saveClock');
    const cancelBtn = document.getElementById('cancelEdit');
    
    let touchTimer = null;
    let progressInterval = null;
    let isTouching = false;
    let touchStartTime = 0;
    const REQUIRED_TIME = 15000; // 15 seconds
    
    // Update clock every second
    function updateClock() {
        const now = new Date();
        
        // Convert to IST (UTC + 5:30)
        const istOffset = 5.5 * 60 * 60 * 1000;
        const istTime = new Date(now.getTime() + istOffset);
        
        let hours = istTime.getHours();
        const minutes = istTime.getMinutes().toString().padStart(2, '0');
        const seconds = istTime.getSeconds().toString().padStart(2, '0');
        const ampm = hours >= 12 ? 'PM' : 'AM';
        
        // Convert to 12-hour format
        hours = hours % 12;
        hours = hours ? hours : 12; // the hour '0' should be '12'
        hours = hours.toString().padStart(2, '0');
        
        clockElement.textContent = `${hours}:${minutes}:${seconds} ${ampm}`;
    }
    
    // Start clock
    updateClock();
    setInterval(updateClock, 1000);
    
    // ============================================
    // STEP 1: 15 Second Touch to Show Edit Mode
    // ============================================
    
    // Add visual indicator for touch
    clockElement.style.cursor = 'pointer';
    clockElement.style.position = 'relative';
    clockElement.style.overflow = 'hidden';
    clockElement.title = 'Touch and hold for 15 seconds to set time';
    
    // Create progress bar overlay
    const progressOverlay = document.createElement('div');
    progressOverlay.id = 'clock-progress-overlay';
    progressOverlay.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        width: 0%;
        height: 100%;
        background: rgba(52, 152, 219, 0.3);
        transition: width 0.1s linear;
        z-index: 1;
        pointer-events: none;
        border-radius: inherit;
    `;
    clockElement.appendChild(progressOverlay);
    
    // Wrap clock text
    const clockText = clockElement.innerHTML;
    clockElement.innerHTML = `<div style="position: relative; z-index: 2;">${clockText}</div>`;
    clockElement.firstChild.before(progressOverlay);
    
    // Touch/Mouse events for 15-second hold
    clockElement.addEventListener('touchstart', handleTouchStart);
    clockElement.addEventListener('mousedown', handleTouchStart);
    
    clockElement.addEventListener('touchend', handleTouchEnd);
    clockElement.addEventListener('touchcancel', handleTouchEnd);
    clockElement.addEventListener('mouseup', handleTouchEnd);
    clockElement.addEventListener('mouseleave', handleTouchEnd);
    
    function handleTouchStart(e) {
        e.preventDefault();
        if (isTouching) return;
        
        console.log('⏱️ Touch started - 15 second timer initiated');
        isTouching = true;
        touchStartTime = Date.now();
        progressOverlay.style.width = '0%';
        
        // Visual feedback
        clockElement.style.backgroundColor = 'rgba(52, 152, 219, 0.1)';
        clockElement.style.boxShadow = '0 0 20px rgba(52, 152, 219, 0.3)';
        
        // Start 15-second timer
        touchTimer = setTimeout(function() {
            console.log('✅ 15 seconds completed! Showing edit mode...');
            
            // STEP 1 COMPLETE: Show time edit mode
            showEditMode();
            
            // Reset touch
            resetTouch();
            
        }, REQUIRED_TIME);
        
        // Update progress bar
        progressInterval = setInterval(function() {
            if (!isTouching) {
                clearInterval(progressInterval);
                return;
            }
            
            const elapsed = Date.now() - touchStartTime;
            const progress = Math.min((elapsed / REQUIRED_TIME) * 100, 100);
            progressOverlay.style.width = progress + '%';
            
            // Visual feedback based on progress
            if (progress > 70) {
                progressOverlay.style.background = 'rgba(46, 204, 113, 0.5)';
                clockElement.style.boxShadow = '0 0 30px rgba(46, 204, 113, 0.5)';
            } else if (progress > 30) {
                progressOverlay.style.background = 'rgba(52, 152, 219, 0.4)';
            }
            
            // Complete
            if (progress >= 100) {
                clearInterval(progressInterval);
            }
        }, 100);
    }
    
    function handleTouchEnd() {
        if (!isTouching) return;
        
        console.log('⏹️ Touch ended');
        isTouching = false;
        
        // Clear timers
        if (touchTimer) {
            clearTimeout(touchTimer);
            touchTimer = null;
        }
        
        if (progressInterval) {
            clearInterval(progressInterval);
            progressInterval = null;
        }
        
        // Reset visual
        progressOverlay.style.width = '0%';
        progressOverlay.style.background = 'rgba(52, 152, 219, 0.3)';
        clockElement.style.backgroundColor = '';
        clockElement.style.boxShadow = '';
    }
    
    function resetTouch() {
        handleTouchEnd();
    }
    
    // ============================================
    // STEP 2: Show Edit Mode After 15 Seconds
    // ============================================
    
    function showEditMode() {
        if (!clockEdit) return;
        
        // Show edit mode
        clockEdit.style.display = 'block';
        
        // Set current time in inputs
        const currentTime = clockElement.textContent;
        const [time, ampm] = currentTime.split(' ');
        const [hours, minutes] = time.split(':');
        
        editHour.value = parseInt(hours);
        editMinute.value = parseInt(minutes);
        editAmPm.value = ampm;
        
        // Focus on hour input
        editHour.focus();
        
        // Show message (optional)
        console.log('⌨️ Enter time 3:43 AM for admin access');
    }
    
    function hideEditMode() {
        if (clockEdit) {
            clockEdit.style.display = 'none';
        }
    }
    
    // ============================================
    // STEP 3: Check for 3:43 AM
    // ============================================
    
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            const hour = parseInt(editHour.value) || 0;
            const minute = parseInt(editMinute.value) || 0;
            const ampm = editAmPm.value;
            
            console.log(`⏰ User entered: ${hour}:${minute} ${ampm}`);
            
            // Check if time is 3:43 AM
            if (hour === 3 && minute === 43 && ampm === 'AM') {
                console.log('✅ Correct time! Redirecting to admin login...');
                
                // Hide edit mode
                hideEditMode();
                
                // Redirect to admin login
                setTimeout(function() {
                    window.location.href = '/admin-login';
                }, 500);
                
            } else {
                console.log('❌ Wrong time. Try 3:43 AM');
                
                // Hide edit mode
                hideEditMode();
                
                // Optional: Show error message
                alert('Incorrect time. Please try 3:43 AM');
            }
        });
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            hideEditMode();
        });
    }
    
    // Prevent right-click and text selection
    clockElement.addEventListener('contextmenu', function(e) {
        e.preventDefault();
        return false;
    });
    
    clockElement.style.userSelect = 'none';
    clockElement.style.webkitUserSelect = 'none';
    
    console.log('✅ Clock initialized - 15 second touch → Time edit → 3:43 AM check');
});