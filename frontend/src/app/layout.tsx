import type { ReactNode } from 'react';
import './globals.css';

export default function RootLayout({ children }: { children: ReactNode }) {
    return (
        <html>
            <head>
                <title>Your App Title</title>
            </head>
            <body>{children}</body>
        </html>
    );
}