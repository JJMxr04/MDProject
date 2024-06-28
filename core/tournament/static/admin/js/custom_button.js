document.addEventListener('DOMContentLoaded', function () {
    console.log('DOMContentLoaded event fired. Running custom_button.js');

    // Adjust the selector to target the correct context where data-custom-detail-url is set
    var objectTools = document.querySelector('.object-tools');

    if (objectTools) {
        console.log('.object-tools element found:', objectTools);

        // Look for the specific link with data-custom-detail-url attribute
        var detailLink = objectTools.querySelector('[data-custom-detail-url]');
        if (detailLink) {
            var detailUrl = detailLink.getAttribute('data-custom-detail-url');
            console.log('data-custom-detail-url found:', detailUrl);

            var detailButton = document.createElement('a');
            detailButton.href = detailUrl;
            detailButton.textContent = 'View Details';
            detailButton.className = 'button';
            detailButton.style.marginLeft = '10px';

            var submitRow = document.querySelector('.submit-row');
            if (submitRow) {
                console.log('.submit-row found. Appending detailButton.');
                submitRow.appendChild(detailButton);
            } else {
                console.error('Submit row element not found.');
            }
        } else {
            console.error('data-custom-detail-url attribute is not found on any child element of .object-tools.');
        }
    } else {
        console.error('.object-tools element not found.');
    }
});
