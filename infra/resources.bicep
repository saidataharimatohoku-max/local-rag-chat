@description('Name prefix used for all resources.')
param namePrefix string

@description('Azure region for all resources.')
param location string

var suffix = uniqueString(resourceGroup().id)
var searchName = '${namePrefix}-search-${suffix}'
var planName = '${namePrefix}-plan-${suffix}'
var webName = '${namePrefix}-web-${suffix}'

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchName
  location: location
  sku: {
    name: 'basic'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

resource web 'Microsoft.Web/sites@2023-12-01' = {
  name: webName
  location: location
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appCommandLine: 'python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000'
      ftpsState: 'Disabled'
      appSettings: [
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: 'https://${search.name}.search.windows.net'
        }
        {
          name: 'AZURE_SEARCH_INDEX'
          value: 'knowledge-index'
        }
      ]
    }
  }
}

output webAppUrl string = 'https://${web.properties.defaultHostName}'
output searchEndpoint string = 'https://${search.name}.search.windows.net'
