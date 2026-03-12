import './globals.css';

export default function RootLayout({ children }) {
    return (
        <html>
            <head>
                <title>Your App Title</title>
            </head>
            <body>{children}</body>
        </html>
    );
}