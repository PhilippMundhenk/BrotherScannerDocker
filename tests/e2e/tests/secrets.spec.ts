import { expect, test } from '@playwright/test';
import { docker, inContainer, readState } from '../helpers';

// The test container gets FTP_PASSWORD_FILE=/run/secrets/ftp_password (a
// bind-mounted file) and no FTP_PASSWORD. The entrypoint must read the file
// into FTP_PASSWORD for the scan scripts and keep it out of everyone's reach.

test.describe('secrets from files', () => {
  test('a *_FILE variable is read into the variable the scripts use', async () => {
    const env = inContainer(['cat', '/opt/brother/scanner/env.txt']);
    expect(env).toContain('FTP_PASSWORD=e2e-secret-password');
    expect(env).not.toContain('FTP_PASSWORD=e2e-secret-password\n\n'); // trailing newline stripped
    expect(docker(['logs', readState().container])).toContain('read FTP_PASSWORD from /run/secrets/ftp_password');
    // the simulator's model is unknown to both Brother drivers: brscan4 with a hint (#173)
    expect(docker(['logs', readState().container])).toContain('scanner driver: brscan4 for model MFC-SIMULATOR');
    expect(docker(['logs', readState().container])).toContain('unknown to both drivers');
  });

  test('the container environment itself does not carry the secret value', async () => {
    const containerEnv = docker(['inspect', '-f', '{{json .Config.Env}}', readState().container]);
    expect(containerEnv).toContain('FTP_PASSWORD_FILE=/run/secrets/ftp_password');
    expect(containerEnv).not.toContain('e2e-secret-password');
  });

  test('env.txt is only readable by the scanner user', async () => {
    expect(inContainer(['stat', '-c', '%a %U', '/opt/brother/scanner/env.txt'])).toBe('600 Scanner');
  });
});
