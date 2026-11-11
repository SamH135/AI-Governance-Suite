const fs = require('fs');
const path = require('path');

class Logger {
    constructor() {
        this.logFile = path.join(__dirname, 'application.log');
        this.ensureLogFileExists();
    }

    ensureLogFileExists() {
        if (!fs.existsSync(this.logFile)) {
            fs.writeFileSync(this.logFile, '');
        }
    }

    formatMessage(level, message, filename = '', functionName = '') {
        const timestamp = new Date().toISOString();
        const location = filename ? `[${filename}${functionName ? `::${functionName}` : ''}]` : '';
        return `${timestamp} [${level}] ${location} ${message}\n`;
    }

    log(level, message, filename = '', functionName = '') {
        const formattedMessage = this.formatMessage(level, message, filename, functionName);
        fs.appendFileSync(this.logFile, formattedMessage);
        console.log(formattedMessage.trim());
    }

    info(message, filename = '', functionName = '') {
        this.log('INFO', message, filename, functionName);
    }

    warn(message, filename = '', functionName = '') {
        this.log('WARN', message, filename, functionName);
    }

    error(message, filename = '', functionName = '') {
        this.log('ERROR', message, filename, functionName);
    }

    debug(message, filename = '', functionName = '') {
        this.log('DEBUG', message, filename, functionName);
    }
}

const logger = new Logger();
module.exports = logger;