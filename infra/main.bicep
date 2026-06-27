targetScope = 'resourceGroup'

@description('Name prefix used for all resources.')
param namePrefix string = 'ragapp'

@description('Azure region for all resources.')
param location string = resourceGroup().location

module resources 'resources.bicep' = {
  name: 'resources'
  params: {
    namePrefix: namePrefix
    location: location
  }
}

output webAppUrl string = resources.outputs.webAppUrl
output searchEndpoint string = resources.outputs.searchEndpoint
