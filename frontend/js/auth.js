/* Supabase email/password login. Configure public URL/key in config.js. */
window.railbotAuthReady = (async () => {
  if (!window.RAILBOT_SUPABASE_URL || !window.RAILBOT_SUPABASE_ANON_KEY) return null;
  const client = window.supabase.createClient(window.RAILBOT_SUPABASE_URL, window.RAILBOT_SUPABASE_ANON_KEY);
  let { data: { session } } = await client.auth.getSession();
  while (!session) {
    const email = prompt('Sign in or create an account. Enter your email:');
    if (!email) throw new Error('Sign-in is required to use chat history.');
    const password = prompt('Enter password (at least 6 characters):');
    if (!password) continue;
    let result = await client.auth.signInWithPassword({ email, password });
    if (result.error) result = await client.auth.signUp({ email, password });
    if (result.error) { alert(result.error.message); continue; }
    if (!result.data.session) { alert('Check your email to confirm your account, then sign in.'); continue; }
    session = result.data.session;
  }
  window.railbotAccessToken = () => client.auth.getSession().then(({data}) => data.session?.access_token);
  window.railbotSignOut = () => client.auth.signOut();
  return session;
})();
