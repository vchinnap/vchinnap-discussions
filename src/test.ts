import { App, TerraformStack } from 'cdktf';
import { AzurermProvider, ResourceGroup, VirtualMachine } from '@cdktf/provider-azurerm';
import { TerraformOutput } from 'cdktf';

class AzureVmControlStack extends TerraformStack {
  constructor(scope: App, id: string) {
    super(scope, id);

    // Azure Provider (you might need to configure this based on your needs)
    new AzurermProvider(this, 'Azure', {
      features: {},
    });

    // Reference an existing Resource Group
    const resourceGroupName = 'your-resource-group-name'; 
    const resourceGroup = ResourceGroup.get(this, 'ExistingResourceGroup', {
      name: resourceGroupName,
    });

    // Reference an existing Virtual Machine
    const vmName = 'your-vm-name'; 
    const existingVm = VirtualMachine.get(this, 'ExistingVirtualMachine', {
      name: vmName,
      resourceGroupName: resourceGroupName,
    });

    // Define Terraform outputs for start/stop commands
    new TerraformOutput(this, 'vmStartCommand', {
      value: `az vm start --resource-group ${resourceGroupName} --name ${vmName}`,
    });

    new TerraformOutput(this, 'vmStopCommand', {
      value: `az vm stop --resource-group ${resourceGroupName} --name ${vmName}`,
    });
  }
}

const app = new App();
new AzureVmControlStack(app, 'azure-vm-control');
app.synth();
