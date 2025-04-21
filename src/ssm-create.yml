import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';
import { Construct } from 'constructs';
import * as cdk from 'aws-cdk-lib';
import { BMOSSMDocumentsConstruct } from './constructs/BMOSSMDocumentsConstruct'; // Assuming your custom construct path

export class CDKSharedSsmDocumentsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const ssmDocumentFiles: string[] = [];

    function GetSsmDocuments(directory: string) {
      fs.readdirSync(directory).forEach((file: string) => {
        const f = path.join(directory, file);
        if (fs.statSync(f).isDirectory()) return GetSsmDocuments(f);
        ssmDocumentFiles.push(f);
      });
    }

    // Step 1: Load SSM document files
    GetSsmDocuments('../service/SharedSsmDocuments/PatchingDocs');

    const ssmDocs = [];

    for (const ssmDocFile of ssmDocumentFiles) {
      let content;
      let docFormat;

      const fileExt = ssmDocFile.split('.').pop()?.toLowerCase();
      if (fileExt?.match(/ya?ml/)) {
        docFormat = 'YAML';
        content = yaml.load(fs.readFileSync(ssmDocFile, { encoding: 'utf-8' }));
      } else if (fileExt?.match(/json/)) {
        docFormat = 'JSON';
        content = JSON.parse(fs.readFileSync(ssmDocFile, 'utf-8'));
      }

      const doc_type = content.schemaVersion && content.schemaVersion.startsWith('2.2')
        ? 'Command'
        : 'Automation';

      const ssmDoc = new BMOSSMDocumentsConstruct(this,
        path.posix.basename(ssmDocFile, path.extname(ssmDocFile)), {
        content: content,
        documentFormat: docFormat,
        documentType: doc_type,
        name: `prefix-${path.posix.basename(ssmDocFile, path.extname(ssmDocFile))}`,
        tags: { Project: 'SSM' },
        versionName: '1.0'
      });

      ssmDocs.push(ssmDoc);
    }
  }
}
