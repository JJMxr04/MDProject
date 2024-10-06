document.addEventListener("DOMContentLoaded", function () {
  const signUpButton = document.getElementById('sign-up-button');
  const addInfoButton = document.getElementById('add-information-button');
  const connectedAccountIdElement = document.getElementById('connected-account-id');
  
  // Helper function to get the CSRF token
  function getCSRFToken() {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
      return csrfToken;
  }

  signUpButton.addEventListener('click', async () => {
      try {
          const response = await fetch('/web/portal/payments/account/', {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
                  'X-CSRFToken': getCSRFToken()  // Add CSRF token to the headers
              },
          });

          if (response.ok) {
              const data = await response.json();
              connectedAccountIdElement.textContent = data.account;
              document.getElementById('creating-connected-account').classList.remove('hidden');
              createAccountLink(data.account);
          } else {
              throw new Error('Failed to create account');
          }
      } catch (error) {
          document.getElementById('error').classList.remove('hidden');
          console.error('Error:', error);
      }
  });

  async function createAccountLink(accountId) {
      try {
          const response = await fetch('/web/portal/payments/account_link/', {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
                  'X-CSRFToken': getCSRFToken()  // Add CSRF token to the headers
              },
              body: JSON.stringify({ account: accountId })
          });

          if (response.ok) {
              const data = await response.json();
              window.location.href = data.url;
          } else {
              throw new Error('Failed to create account link');
          }
      } catch (error) {
          document.getElementById('error').classList.remove('hidden');
          console.error('Error:', error);
      }
  }
});
