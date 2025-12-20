// Real Time Clock with IST and Secret Admin Access
document.addEventListener('DOMContentLoaded', function() {
    const clockElement = document.getElementById('realTimeClock');
    const clockEdit = document.getElementById('clockEdit');
    const editHour = document.getElementById('editHour');
    const editMinute = document.getElementById('editMinute');
    const editAmPm = document.getElementById('editAmPm');
    const saveBtn = document.getElementById('saveClock');
    const cancelBtn = document.getElementById('cancelEdit');
    
    let longPressTimer = null;
    let tapCount = 0;
    let isLongPress = false;
    
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
    
    // Secret Admin Access: Long Press (15 seconds) + 5 Taps
    clockElement.addEventListener('mousedown', startLongPress);
    clockElement.addEventListener('touchstart', startLongPress);
    
    clockElement.addEventListener('mouseup', endLongPress);
    clockElement.addEventListener('touchend', endLongPress);
    clockElement.addEventListener('mouseleave', cancelLongPress);
    
    clockElement.addEventListener('click', handleTap);
    
    function startLongPress(e) {
        e.preventDefault();
        isLongPress = false;
        longPressTimer = setTimeout(() => {
            isLongPress = true;
            // Long press detected (15 seconds)
            // No visual feedback - completely hidden
        }, 15000); // 15 seconds
    }
    
    function endLongPress() {
        if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
    }
    
    function cancelLongPress() {
        if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
        // Reset tap count if user leaves during long press
        tapCount = 0;
    }
    
    function handleTap(e) {
        e.preventDefault();
        
        if (isLongPress) {
            tapCount++;
            
            if (tapCount >= 5) {
                // Success! Show edit mode
                showEditMode();
                tapCount = 0;
                isLongPress = false;
            }
        } else {
            // Reset if not in long press mode
            tapCount = 0;
        }
    }
    
    function showEditMode() {
        clockEdit.style.display = 'block';
        const currentTime = clockElement.textContent;
        const [time, ampm] = currentTime.split(' ');
        const [hours, minutes] = time.split(':');
        
        editHour.value = parseInt(hours);
        editMinute.value = parseInt(minutes);
        editAmPm.value = ampm;
        
        editHour.focus();
    }
    
    function hideEditMode() {
        clockEdit.style.display = 'none';
        editHour.value = '';
        editMinute.value = '';
        tapCount = 0;
        isLongPress = false;
    }
    
    saveBtn.addEventListener('click', function() {
        const hour = parseInt(editHour.value);
        const minute = parseInt(editMinute.value);
        const ampm = editAmPm.value;
        
        // Check if time is 3:43
        if (hour === 3 && minute === 43) {
            // Correct code! Redirect to admin login
            window.location.href = '/admin-login';
        } else {
            // Wrong time, hide edit mode
            hideEditMode();
            // No feedback to user - completely hidden
        }
    });
    
    cancelBtn.addEventListener('click', hideEditMode);
    
    // Prevent right-click and text selection
    clockElement.addEventListener('contextmenu', function(e) {
        e.preventDefault();
        return false;
    });
    
    clockElement.style.userSelect = 'none';
    clockElement.style.webkitUserSelect = 'none';
});
