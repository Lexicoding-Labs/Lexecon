import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Login from './Login';
import { AuthAPI } from '../api/endpoints';
import { ThemeProvider } from '../contexts/ThemeContext';

jest.mock('../api/endpoints', () => ({
  AuthAPI: { login: jest.fn(), changePassword: jest.fn(), me: jest.fn(), health: jest.fn() },
}));

test('required password change stays restricted until the new password succeeds', async () => {
  AuthAPI.health.mockResolvedValue({ data: { status: 'healthy' } });
  localStorage.removeItem('lexecon_token');
  AuthAPI.login
    .mockResolvedValueOnce({ data: { success: false, session_id: 'restricted', error: 'Password change required' } })
    .mockResolvedValueOnce({ data: { success: true, session_id: 'full', user: { username: 'operator' } } });
  AuthAPI.changePassword.mockResolvedValue({ data: { success: true } });
  render(<ThemeProvider><Login /></ThemeProvider>);
  fireEvent.change(screen.getByPlaceholderText('Your username'), { target: { value: 'operator' } });
  fireEvent.change(screen.getByPlaceholderText('Your password'), { target: { value: 'Old!Pass123' } });
  fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
  await screen.findByRole('button', { name: 'Change Password' });
  expect(localStorage.getItem('lexecon_token')).toBeNull();
  fireEvent.change(screen.getByPlaceholderText('Your password'), { target: { value: 'Old!Pass123' } });
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'New!Pass123' } });
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'New!Pass123' } });
  fireEvent.click(screen.getByRole('button', { name: 'Change Password' }));
  await waitFor(() => expect(AuthAPI.changePassword).toHaveBeenCalledWith('restricted', 'Old!Pass123', 'New!Pass123'));
  await waitFor(() => expect(localStorage.getItem('lexecon_token')).toBe('full'));
});

test('offline API gives a local startup instruction and can retry', async () => {
  AuthAPI.health.mockRejectedValueOnce(new Error('Network Error')).mockResolvedValueOnce({ data: { status: 'healthy' } });
  render(<ThemeProvider><Login /></ThemeProvider>);
  expect((await screen.findByRole('alert')).textContent).toContain('python3 scripts/start-local.py');
  fireEvent.click(screen.getByRole('button', { name: 'Retry connection' }));
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
});
