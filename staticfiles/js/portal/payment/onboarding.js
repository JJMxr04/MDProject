document.addEventListener("DOMContentLoaded", function () {
    const signUpButton = document.getElementById('sign-up-button');
    const addInfoButton = document.getElementById('add-information-button');
    const connectedAccountIdElement = document.getElementById('connected-account-id');
  
    signUpButton.addEventListener('click', async () => {
      try {
        const response = await fetch('/account/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
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
        const response = await fetch('/account_link/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
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
  