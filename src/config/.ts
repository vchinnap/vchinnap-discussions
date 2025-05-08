import * as fs from 'fs';
import * as path from 'path';

const documentContent = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, '../../../service/remediations/evaluation-ssm-content.json'),
    'utf8'
  )
);
